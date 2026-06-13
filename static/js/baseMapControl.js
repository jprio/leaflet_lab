
const demSourceMaptiler = new mlcontour.DemSource({
    url: 'https://api.maptiler.com/tiles/terrain-rgb-v2/{z}/{x}/{y}.webp?key=TJBqVnX8a4CMqkunq4W0',
    encoding: 'mapbox',
    maxzoom: 12,
    // offload contour line computation to a web worker
    worker: true
});

const demSource = new mlcontour.DemSource({
    url: "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
    encoding: "terrarium",
    maxzoom: 15,
    worker: true,
    cacheSize: 100,
    timeoutMs: 10_000,
})
// console.log(initialStyle);
demSource.setupMaplibre(maplibregl);
const osm2 = {
    name: "Open Street Map",
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    maxzoom: 18,
    attribution: 'osm'
}
const osmHot = {
    name: "OSM Hot",
    tiles: ['https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png'],
}
const osmCycle = {
    name: "OSM Cycle",
    tiles: ['https://a.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png'],
}
const arcgisHybrid = {
    name: "ArcGis Hybrid",
    tiles: ['https://raw.githubusercontent.com/go2garret/maps/main/src/assets/json/arcgis_hybrid.json'],
    maxzoom: 13,
    attribution: 'Tiles &copy; Esri &mdash; Source: USGS, Esri, TANA, DeLorme, and NPS',
}
const google_terrain = {
    name: "Google Maps Terrain",
    type: 'raster',
    tiles: ['https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}'],
    tileSize: 256,
    attribution: '&copy; Google Maps'
}
const google_road = {
    name: "Google Maps Road",
    type: 'raster',
    tiles: ['https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}'],
    tileSize: 256,
    attribution: '&copy; Google Maps'
}

const google_sat = {
    name: "Google Maps Satellite",
    type: 'raster',
    tiles: ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'],
    tileSize: 256,
    attribution: '&copy; Google Maps'
}

const baseLayers = {
    osm2,
    osmHot,
    osmCycle,
    arcgisHybrid,
    google_terrain,
    google_road,
    google_sat
}
const basemapControl = new BasemapControl({ basemaps: baseLayers, initialBasemap: "google_terrain", width: "200px" });

let currentTracksGeoJSON = null;
let currentFilterState = {
    collectionId: '',
    name: '',
    type: '',
    minLength: null,
    maxLength: null
};
