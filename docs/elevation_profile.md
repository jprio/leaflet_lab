# Utilisation dans index.html

```javascript
<div id="elevation"></div>

<script type="module">
    import {
        ElevationProfile,
        renderElevationProfile
    } from "./js/elevation_jp.js";

    const profile = new ElevationProfile(lineString);

    renderElevationProfile(
        document.getElementById("elevation"),
        profile,
        800,
        200
    );
</script>
```

# Synchronisation avec MapLibre
Dans ton index.html ou ton fichier principal :

```javascript
const hoverMarker = new maplibregl.Marker({
    color: "red"
});

const elevationDiv =
    document.getElementById("elevation");

elevationDiv.addEventListener("profile-hover", event => {
    const point = event.detail;

    hoverMarker
        .setLngLat([point.lon, point.lat])
        .addTo(map);
});

elevationDiv.addEventListener("profile-leave", () => {
    hoverMarker.remove();
});`
```