// Elevation profile UI and interactions
let currentElevations = null;
let currentTrailFeature = null;
let profileMarker = null;
let elevationHoverInitialized = false;
let currentProfileRenderMeta = null; // will hold smoothing, extents and layout
let profileCursorEl = null;

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
profileContainer.style.width = '1000px';
profileContainer.style.maxHeight = '350px';
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

// small dot that follows the mouse on the profile canvas
profileCursorEl = document.createElement('div');
profileCursorEl.id = 'elevation-profile-cursor';
profileCursorEl.style.position = 'absolute';
profileCursorEl.style.width = '10px';
profileCursorEl.style.height = '10px';
profileCursorEl.style.borderRadius = '50%';
profileCursorEl.style.background = '#4CAF50';
profileCursorEl.style.boxShadow = '0 1px 4px rgba(0,0,0,0.25)';
profileCursorEl.style.transform = 'translate(-50%, -50%)';
profileCursorEl.style.pointerEvents = 'none';
profileCursorEl.style.display = 'none';
canvasContainer.appendChild(profileCursorEl);

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
    btn.style.fontSize = '14px';
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


const tmpCanvas = document.createElement('canvas');
tmpCanvas.width = 256; tmpCanvas.height = 256;
const tmpCtx = tmpCanvas.getContext('2d');

async function getElevationAt(lon, lat, z = 10) {
    // Query terrain for elevation
    const elevation = map.terrain.getElevationForLngLatZoom(
        new maplibregl.LngLat(lon, lat),
        13
    );
    // console.log(`Elevation at (${lon.toFixed(5)}, ${lat.toFixed(5)}) for zoom ${map.getZoom()}:`, elevation);
    return elevation !== undefined ? elevation : null;

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
    const hasGeoZ = pts.every((pt) => Array.isArray(pt) && pt.length >= 3 && typeof pt[2] === 'number');

    for (let i = 1; i < pts.length; i++) {
        const d = haversine([pts[i - 1][0], pts[i - 1][1]], [pts[i][0], pts[i][1]]);
        const dz = hasGeoZ ? (pts[i][2] - pts[i - 1][2]) : null;
        segs.push({ from: pts[i - 1], to: pts[i], dist: d, dz });
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
            if (acc + seg.dist >= target || seg === segs[segs.length - 1]) {
                const remain = target - acc;
                const frac = seg.dist === 0 ? 0 : remain / seg.dist;
                const lon = seg.from[0] + (seg.to[0] - seg.from[0]) * frac;
                const lat = seg.from[1] + (seg.to[1] - seg.from[1]) * frac;
                const distance = t * total;
                let elevation = null;
                if (hasGeoZ) {
                    elevation = seg.from[2] + dz * frac;
                    if (elevation === null) {
                        elevation = seg.from[2];
                    }
                }
                res.push({ lon, lat, distance, elevation });
                break;
            }
            acc += seg.dist;
        }
    }

    if (hasGeoZ) {
        return res;
    }

    const elevations = [];
    for (let i = 0; i < res.length; i++) {
        const lon = res[i].lon, lat = res[i].lat;
        const elev = await getElevationAt(lon, lat, 13);
        elevations.push({ lon, lat, distance: res[i].distance, elevation: elev });
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

    // Build arrays for smoothing and drawing. Use 0 where elevation missing.
    const vals = elevations.map(e => (e && typeof e.elevation === 'number') ? e.elevation : 0);
    const lons = elevations.map(e => e.lon || 0);
    const lats = elevations.map(e => e.lat || 0);
    const distances = elevations.map(e => e.distance || 0);

    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const range = max - min || 1;

    const padLeft = 65;
    const padRight = 15;
    const padTop = 15;
    const padBottom = 35;
    const graphW = w - padLeft - padRight;
    const graphH = h - padTop - padBottom;

    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, w, h);

    ctx.strokeStyle = '#e8e8e8';
    ctx.lineWidth = 1;
    // larger font for altitude labels for readability
    ctx.font = '15px sans-serif';
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

    // Smooth each numeric series so the profile and hover align
    const smoothVals = generateSmoothCurve(vals);
    const smoothLons = generateSmoothCurve(lons);
    const smoothLats = generateSmoothCurve(lats);
    const smoothDistances = generateSmoothCurve(distances);

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

    // larger font for distance labels
    ctx.font = '16px sans-serif';
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

    // store render meta for hover interaction
    currentProfileRenderMeta = {
        min, max, range,
        padLeft, padRight, padTop, padBottom, graphW, graphH,
        smoothVals, smoothLons, smoothLats, smoothDistances
    };
    // hide profile cursor initially
    if (profileCursorEl) profileCursorEl.style.display = 'none';
}

async function showElevationProfile(feature) {
    console.log("Generating elevation profile for feature:", feature);
    if (!feature || !feature.geometry) return;
    let coords = feature.geometry.coordinates;
    if (feature.geometry.type === 'MultiLineString' || feature.geometry.type === 'MultiLineSring') {
        coords = coords.flat();
    }
    const elevations = await sampleLineElevations(coords);
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
        if (!currentProfileRenderMeta) return;
        const meta = currentProfileRenderMeta;
        const cssWidth = rect.width;
        const cssHeight = rect.height;
        const padLeftCss = meta.padLeft * (cssWidth / 840);
        const padRightCss = meta.padRight * (cssWidth / 840);
        const padTopCss = meta.padTop * (cssHeight / 220);
        const padBottomCss = meta.padBottom * (cssHeight / 220);
        const graphW = cssWidth - padLeftCss - padRightCss;
        const graphH = cssHeight - padTopCss - padBottomCss;

        const x = e.clientX - rect.left;
        if (x < padLeftCss || x > cssWidth - padRightCss) return;
        const relX = (x - padLeftCss) / graphW;
        const smoothLen = meta.smoothVals.length;
        const pointIndex = Math.round(relX * (smoothLen - 1));

        if (pointIndex >= 0 && pointIndex < smoothLen) {
            const lon = meta.smoothLons[pointIndex];
            const lat = meta.smoothLats[pointIndex];
            const elev = meta.smoothVals[pointIndex];

            // position map marker
            if (profileMarker) {
                profileMarker.setLngLat([lon, lat]);
            } else {
                profileMarker = new maplibregl.Marker({ color: '#4CAF50', scale: 0.8 })
                    .setLngLat([lon, lat])
                    .addTo(map);
            }

            // position cursor on canvas container
            const xPos = padLeftCss + (pointIndex / (smoothLen - 1)) * graphW;
            const yPos = padTopCss + graphH * (1 - (elev - meta.min) / meta.range);
            if (profileCursorEl) {
                profileCursorEl.style.left = `${xPos}px`;
                profileCursorEl.style.top = `${yPos}px`;
                profileCursorEl.style.display = 'block';
            }
        }
    });

    canvas.addEventListener('mouseleave', () => {
        if (profileMarker) {
            profileMarker.remove();
            profileMarker = null;
        }
        if (profileCursorEl) profileCursorEl.style.display = 'none';
    });
}

map.addControl(new ToggleProfileControl(), 'bottom-left');
