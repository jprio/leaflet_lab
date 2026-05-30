// Elevation profile UI and interactions
let currentElevations = null;
let currentTrailFeature = null;
let profileMarker = null;
let elevationHoverInitialized = false;

// Create profile UI elements
const profileContainer = document.createElement('div');
profileContainer.id = 'elevation-profile';
profileContainer.className = 'elevation-profile-control';
profileContainer.style.position = 'absolute';
profileContainer.style.left = '10px';
profileContainer.style.bottom = '10px';
profileContainer.style.zIndex = 999;
profileContainer.style.padding = '16px';
profileContainer.style.display = 'none';
profileContainer.style.width = '420px';
profileContainer.style.maxHeight = '320px';
profileContainer.style.overflowY = 'auto';
profileContainer.style.boxSizing = 'border-box';

const title = document.createElement('div');
title.id = 'elevation-profile-title';
profileContainer.appendChild(title);

const canvasContainer = document.createElement('div');
canvasContainer.style.position = 'relative';
canvasContainer.style.marginTop = '8px';

const canvas = document.createElement('canvas');
canvas.width = 840; // logical pixels for high-DPI
canvas.height = 220;
canvas.style.width = '100%';
canvas.style.height = '220px';
canvas.id = 'elevation-profile-canvas';
canvasContainer.appendChild(canvas);

const hoverInfo = document.createElement('div');
hoverInfo.id = 'elevation-profile-info-hover';
canvasContainer.appendChild(hoverInfo);

profileContainer.appendChild(canvasContainer);

const info = document.createElement('div');
info.id = 'elevation-profile-info';
profileContainer.appendChild(info);

const closeBtn = document.createElement('button');
closeBtn.textContent = '✕';
closeBtn.title = 'Close profile';
closeBtn.style.position = 'absolute';
closeBtn.style.right = '10px';
closeBtn.style.top = '10px';
closeBtn.style.border = 'none';
closeBtn.style.background = 'transparent';
closeBtn.style.fontSize = '18px';
closeBtn.style.cursor = 'pointer';
closeBtn.style.color = '#666';
closeBtn.style.padding = '0';
closeBtn.style.width = '24px';
closeBtn.style.height = '24px';
closeBtn.style.display = 'flex';
closeBtn.style.alignItems = 'center';
closeBtn.style.justifyContent = 'center';
closeBtn.onclick = () => { profileContainer.style.display = 'none'; };
profileContainer.appendChild(closeBtn);

document.body.appendChild(profileContainer);

function ToggleProfileControl() { }
ToggleProfileControl.prototype.onAdd = function (mapInstance) {
    this._map = mapInstance;
    this._container = document.createElement('div');
    this._container.className = 'maplibregl-ctrl maplibregl-ctrl-group';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.title = 'Toggle elevation profile';
    btn.textContent = 'Profile';
    btn.style.padding = '6px 8px';
    btn.style.fontSize = '12px';
    btn.onclick = () => {
        if (profileContainer.style.display === 'none' || !profileContainer.style.display) {
            profileContainer.style.display = 'block';
        } else {
            profileContainer.style.display = 'none';
        }
    };
    this._container.appendChild(btn);
    return this._container;
};
ToggleProfileControl.prototype.onRemove = function () {
    if (this._container && this._container.parentNode) this._container.parentNode.removeChild(this._container);
    this._map = undefined;
};

function terrariumDecode(r, g, b) {
    return ((r * 256 + g + b / 256) - 32768);
}

function lonLatToPixelInTile(lon, lat, z) {
    const xtile = (lon + 180) / 360 * Math.pow(2, z);
    const ytile = (1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, z);
    const x = Math.floor((xtile - Math.floor(xtile)) * 256);
    const y = Math.floor((ytile - Math.floor(ytile)) * 256);
    const tx = Math.floor(xtile);
    const ty = Math.floor(ytile);
    return { z, tx, ty, px: x, py: y };
}

const tileCache = new Map();

async function fetchTileImage(z, x, y) {
    const key = `${z}/${x}/${y}`;
    if (tileCache.has(key)) return tileCache.get(key);
    const url = `https://s3.amazonaws.com/elevation-tiles-prod/terrarium/${z}/${x}/${y}.png`;
    const img = new Image();
    img.crossOrigin = 'Anonymous';
    const p = new Promise((resolve, reject) => {
        img.onload = () => resolve(img);
        img.onerror = reject;
    });
    img.src = url;
    const loaded = await p;
    tileCache.set(key, loaded);
    return loaded;
}

const tmpCanvas = document.createElement('canvas');
tmpCanvas.width = 256; tmpCanvas.height = 256;
const tmpCtx = tmpCanvas.getContext('2d');

async function getElevationAt(lon, lat, z = 13) {
    const { z: zz, tx, ty, px, py } = lonLatToPixelInTile(lon, lat, z);
    try {
        const img = await fetchTileImage(zz, tx, ty);
        tmpCtx.clearRect(0, 0, 256, 256);
        tmpCtx.drawImage(img, 0, 0);
        const d = tmpCtx.getImageData(px, py, 1, 1).data;
        return terrariumDecode(d[0], d[1], d[2]);
    } catch (err) {
        console.warn('Tile fetch/read failed', err);
        return null;
    }
}

function haversine([lon1, lat1], [lon2, lat2]) {
    const R = 6371000;
    const toRad = v => v * Math.PI / 180;
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

async function sampleLineElevations(coordinates, samples = null) {
    const pts = coordinates;
    const segs = [];
    let total = 0;
    for (let i = 1; i < pts.length; i++) {
        const d = haversine([pts[i - 1][0], pts[i - 1][1]], [pts[i][0], pts[i][1]]);
        segs.push({ from: pts[i - 1], to: pts[i], dist: d });
        total += d;
    }
    const res = [];
    if (total === 0) return res;

    if (samples === null || typeof samples === 'undefined') {
        const perMeter = 1 / 5;
        const estimated = Math.floor(total * perMeter);
        samples = Math.min(200, Math.max(30, estimated));
    }

    for (let s = 0; s < samples; s++) {
        const t = s / (samples - 1);
        const target = t * total;
        let acc = 0;
        for (const seg of segs) {
            if (acc + seg.dist >= target) {
                const remain = target - acc;
                const frac = seg.dist === 0 ? 0 : remain / seg.dist;
                const lon = seg.from[0] + (seg.to[0] - seg.from[0]) * frac;
                const lat = seg.from[1] + (seg.to[1] - seg.from[1]) * frac;
                res.push([lon, lat, t * total]);
                break;
            }
            acc += seg.dist;
        }
    }

    const elevations = [];
    for (let i = 0; i < res.length; i++) {
        const lon = res[i][0], lat = res[i][1];
        const elev = await getElevationAt(lon, lat, 13);
        elevations.push({ lon, lat, distance: res[i][2], elevation: elev });
    }
    return elevations;
}

function catmullRom(p0, p1, p2, p3, t) {
    const v0 = (p2 - p0) * 0.5;
    const v1 = (p3 - p1) * 0.5;
    const t2 = t * t;
    const t3 = t * t2;
    return (2 * p1 - 2 * p2 + v0 + v1) * t3 + (-3 * p1 + 3 * p2 - 2 * v0 - v1) * t2 + v0 * t + p1;
}

function generateSmoothCurve(points) {
    if (points.length < 2) return points;
    const smooth = [];
    for (let i = 0; i < points.length - 1; i++) {
        const p0 = points[Math.max(i - 1, 0)];
        const p1 = points[i];
        const p2 = points[i + 1];
        const p3 = points[Math.min(i + 2, points.length - 1)];
        smooth.push(p1);
        for (let j = 1; j <= 4; j++) {
            const t = j / 5;
            const val = catmullRom(p0, p1, p2, p3, t);
            smooth.push(val);
        }
    }
    smooth.push(points[points.length - 1]);
    return smooth;
}

function renderProfile(elevations, featureProps) {
    const canvasEl = document.getElementById('elevation-profile-canvas');
    const ctx = canvasEl.getContext('2d');
    const w = canvasEl.width;
    const h = canvasEl.height;

    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = w * dpr;
    canvasEl.height = h * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, w, h);
    if (!elevations || elevations.length === 0) return;

    currentElevations = elevations;

    const vals = elevations.map(e => e.elevation === null ? 0 : e.elevation);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;

    const padLeft = 45;
    const padRight = 15;
    const padTop = 15;
    const padBottom = 35;
    const graphW = w - padLeft - padRight;
    const graphH = h - padTop - padBottom;

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = '#e8e8e8';
    ctx.lineWidth = 1;
    ctx.font = '11px sans-serif';
    ctx.fillStyle = '#999';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';

    for (let g = 0; g <= 5; g++) {
        const y = padTop + (graphH / 5) * g;
        const elev = max - (range / 5) * g;
        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(w - padRight, y);
        ctx.stroke();
        ctx.fillStyle = '#888';
        ctx.fillText(Math.round(elev) + ' m', padLeft - 8, y);
    }

    const smoothVals = generateSmoothCurve(vals);

    ctx.beginPath();
    for (let i = 0; i < smoothVals.length; i++) {
        const x = padLeft + (i / (smoothVals.length - 1)) * graphW;
        const value = smoothVals[i];
        const y = padTop + graphH * (1 - (value - min) / range);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.lineTo(w - padRight, padTop + graphH);
    ctx.lineTo(padLeft, padTop + graphH);
    ctx.closePath();

    const gradient = ctx.createLinearGradient(0, padTop, 0, padTop + graphH);
    gradient.addColorStop(0, 'rgba(76, 175, 80, 0.3)');
    gradient.addColorStop(1, 'rgba(76, 175, 80, 0.05)');
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    for (let i = 0; i < smoothVals.length; i++) {
        const x = padLeft + (i / (smoothVals.length - 1)) * graphW;
        const value = smoothVals[i];
        const y = padTop + graphH * (1 - (value - min) / range);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = '#4CAF50';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.stroke();

    ctx.font = '11px sans-serif';
    ctx.fillStyle = '#888';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';

    const totalDist = elevations.length ? elevations[elevations.length - 1].distance : 0;
    const distInterval = Math.ceil(totalDist / 4 / 1000) * 1000;
    for (let d = 0; d <= totalDist; d += distInterval) {
        const ratio = d / totalDist;
        const x = padLeft + ratio * graphW;
        ctx.fillText((d / 1000).toFixed(1) + ' km', x, padTop + graphH + 5);
    }

    let gain = 0, loss = 0;
    for (let i = 1; i < elevations.length; i++) {
        const curr = elevations[i].elevation === null ? 0 : elevations[i].elevation;
        const prev = elevations[i - 1].elevation === null ? 0 : elevations[i - 1].elevation;
        const diff = curr - prev;
        if (diff > 0) gain += diff;
        else loss += Math.abs(diff);
    }

    const titleEl = document.getElementById('elevation-profile-title');
    titleEl.textContent = featureProps && featureProps.name ? featureProps.name : 'Elevation profile';

    const infoEl = document.getElementById('elevation-profile-info');
    infoEl.innerHTML = `
        <div>
            <div>
                <div class="elevation-stat-label">Distance</div>
                <div class="elevation-stat-value">${(totalDist / 1000).toFixed(2)} km</div>
            </div>
        </div>
        <div>
            <div>
                <div class="elevation-stat-label">Elevation Gain</div>
                <div class="elevation-stat-value elevation-stat-gain">↑ ${Math.round(gain)} m</div>
            </div>
        </div>
        <div>
            <div>
                <div class="elevation-stat-label">Elevation Loss</div>
                <div class="elevation-stat-value elevation-stat-loss">↓ ${Math.round(loss)} m</div>
            </div>
        </div>
        <div>
            <div>
                <div class="elevation-stat-label">Min / Max</div>
                <div class="elevation-stat-value">${Math.round(min)} / ${Math.round(max)} m</div>
            </div>
        </div>
    `;

    profileContainer.style.display = 'block';
}

async function showElevationProfile(feature) {
    if (!feature || !feature.geometry) return;
    let coords = feature.geometry.coordinates;
    if (feature.geometry.type === 'MultiLineString') {
        coords = coords.flat();
    }
    const pts = coords.map(c => [c[0], c[1]]);
    const elevations = await sampleLineElevations(pts);
    currentTrailFeature = feature;
    renderProfile(elevations, feature.properties || {});
    setupProfileHoverInteraction(elevations);
}

function setupProfileHoverInteraction(elevations) {
    const canvas = document.getElementById('elevation-profile-canvas');
    if (canvas._elevationHoverInitialized) return;
    canvas._elevationHoverInitialized = true;

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const padLeft = 45 * (rect.width / 840);
        const padRight = 15 * (rect.width / 840);
        const graphWidth = rect.width - padLeft - padRight;

        if (x < padLeft || x > rect.width - padRight) return;
        const relX = (x - padLeft) / graphWidth;
        const pointIndex = Math.round(relX * (elevations.length - 1));

        if (pointIndex >= 0 && pointIndex < elevations.length) {
            const point = elevations[pointIndex];
            if (profileMarker) {
                profileMarker.setLngLat([point.lon, point.lat]);
            } else {
                profileMarker = new maplibregl.Marker({
                    color: '#4CAF50',
                    scale: 0.8
                })
                    .setLngLat([point.lon, point.lat])
                    .addTo(map);
            }
        }
    });

    canvas.addEventListener('mouseleave', () => {
        if (profileMarker) {
            profileMarker.remove();
            profileMarker = null;
        }
    });
}

map.addControl(new ToggleProfileControl(), 'bottom-left');
