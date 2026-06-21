import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { makeT, chanceWord, pct0, r1, nearestAsset } from '../i18n.js'

// Plain-Leaflet map wrapped in React. We avoid react-leaflet to keep tight
// control over georeferenced ImageOverlays (risk + burn-probability) and the
// click-to-ignite handler. Overlays are updated via setUrl so the burn-spread
// animation swaps frames smoothly without flicker.
export default function MapView({
  bounds, riskImage, burnImage, showRisk, showBurn,
  ignition, assets = [], firepoints = [], showFire,
  recommendation, showRec, lang = 'th', onClick,
  riskMlImage, showRiskMl,
  nationalImage, nationalBounds, showNational,
  aoiGeojson,
}) {
  const elRef = useRef(null)
  const mapRef = useRef(null)
  const lyr = useRef({})
  const boundsRef = useRef(null)
  const clickRef = useRef(onClick)
  clickRef.current = onClick

  // init once
  useEffect(() => {
    const map = L.map(elRef.current, { zoomControl: true, attributionControl: true })
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map)
    L.control.scale({ metric: true, imperial: false, position: 'bottomright' }).addTo(map)
    map.setView([18.79, 98.9], 12)
    map.on('click', (e) => clickRef.current && clickRef.current(e.latlng.lat, e.latlng.lng))
    mapRef.current = map
    if (typeof window !== 'undefined') { window.__map = map; window.__L = L } // for debugging

    // The container is often 0x0 on first paint (which makes fitBounds clamp to
    // max zoom). Re-fit whenever it gains/changes size, once bounds are known.
    const fit = () => {
      const el = elRef.current
      if (!el) return
      map.invalidateSize()
      if (boundsRef.current && el.clientWidth > 50 && el.clientHeight > 50) {
        map.fitBounds(L.latLngBounds(boundsRef.current), { padding: [12, 12] })
      }
    }
    const ro = new ResizeObserver(fit)
    ro.observe(elRef.current)
    return () => { ro.disconnect(); map.remove(); mapRef.current = null }
  }, [])

  // remember bounds + fit immediately if the container already has a real size
  useEffect(() => {
    boundsRef.current = bounds
    const map = mapRef.current
    const el = elRef.current
    if (!bounds || !map || !el) return
    map.invalidateSize()
    if (el.clientWidth > 50 && el.clientHeight > 50) {
      map.fitBounds(L.latLngBounds(bounds), { padding: [12, 12] })
    }
  }, [JSON.stringify(bounds)])

  // outline the study area: real province border when available, else the bbox
  useEffect(() => {
    const map = mapRef.current
    if (!map || !bounds) return
    if (lyr.current.aoi) { map.removeLayer(lyr.current.aoi); lyr.current.aoi = null }
    if (aoiGeojson) {
      lyr.current.aoi = L.geoJSON(aoiGeojson, {
        style: { color: '#ffd166', weight: 2, fill: false, interactive: false },
      }).addTo(map)
    } else {
      lyr.current.aoi = L.rectangle(L.latLngBounds(bounds), {
        color: '#ffd166', weight: 2, fill: false, dashArray: '6 6', interactive: false,
      }).addTo(map)
    }
  }, [JSON.stringify(bounds), aoiGeojson])

  // risk overlay
  useEffect(() => {
    const map = mapRef.current
    if (!map || !bounds) return
    if (!showRisk || !riskImage) {
      if (lyr.current.risk) { map.removeLayer(lyr.current.risk); lyr.current.risk = null }
      return
    }
    if (!lyr.current.risk) {
      lyr.current.risk = L.imageOverlay(riskImage, bounds, { opacity: 0.7, interactive: false }).addTo(map)
    } else {
      lyr.current.risk.setUrl(riskImage)
      lyr.current.risk.setBounds(L.latLngBounds(bounds))
    }
  }, [riskImage, showRisk, JSON.stringify(bounds)])

  // national overview overlay + zoom to country / back to local
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (lyr.current.national) { map.removeLayer(lyr.current.national); lyr.current.national = null }
    if (showNational && nationalImage && nationalBounds) {
      lyr.current.national = L.imageOverlay(nationalImage, nationalBounds, { opacity: 0.8, interactive: false }).addTo(map)
      map.fitBounds(L.latLngBounds(nationalBounds), { padding: [10, 10] })
    } else if (boundsRef.current) {
      map.fitBounds(L.latLngBounds(boundsRef.current), { padding: [12, 12] })
    }
  }, [showNational, nationalImage, JSON.stringify(nationalBounds)])

  // ML fire-susceptibility overlay
  useEffect(() => {
    const map = mapRef.current
    if (!map || !bounds) return
    if (!showRiskMl || !riskMlImage) {
      if (lyr.current.riskml) { map.removeLayer(lyr.current.riskml); lyr.current.riskml = null }
      return
    }
    if (!lyr.current.riskml) {
      lyr.current.riskml = L.imageOverlay(riskMlImage, bounds, { opacity: 0.7, interactive: false }).addTo(map)
    } else {
      lyr.current.riskml.setUrl(riskMlImage)
      lyr.current.riskml.setBounds(L.latLngBounds(bounds))
    }
  }, [riskMlImage, showRiskMl, JSON.stringify(bounds)])

  // burn-probability overlay (animated via setUrl)
  useEffect(() => {
    const map = mapRef.current
    if (!map || !bounds) return
    if (!showBurn || !burnImage) {
      if (lyr.current.burn) { map.removeLayer(lyr.current.burn); lyr.current.burn = null }
      return
    }
    if (!lyr.current.burn) {
      lyr.current.burn = L.imageOverlay(burnImage, bounds, { opacity: 0.82, interactive: false }).addTo(map)
    } else {
      lyr.current.burn.setUrl(burnImage)
    }
    lyr.current.burn.setZIndex(450)
  }, [burnImage, showBurn, JSON.stringify(bounds)])

  // ignition marker
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (lyr.current.ign) { map.removeLayer(lyr.current.ign); lyr.current.ign = null }
    if (ignition) {
      const icon = L.divIcon({ className: '', html: '🔥', iconSize: [26, 26], iconAnchor: [13, 13] })
      lyr.current.ign = L.marker([ignition.lat, ignition.lon], { icon }).addTo(map)
    }
  }, [ignition && ignition.lat, ignition && ignition.lon])

  // assets to protect
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (lyr.current.assets) map.removeLayer(lyr.current.assets)
    const g = L.layerGroup()
    assets.forEach((a) => {
      const icon = L.divIcon({ className: '', html: '🏠', iconSize: [20, 20], iconAnchor: [10, 10] })
      L.marker([a.lat, a.lon], { icon }).bindTooltip(a.name).addTo(g)
    })
    g.addTo(map)
    lyr.current.assets = g
  }, [JSON.stringify(assets)])

  // historical FIRMS hotspots
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (lyr.current.fire) { map.removeLayer(lyr.current.fire); lyr.current.fire = null }
    if (showFire && firepoints.length) {
      const g = L.layerGroup()
      firepoints.forEach((p) => {
        L.circleMarker([p.lat, p.lon], {
          radius: 4, color: '#ff2d2d', fillColor: '#ff5b3d', fillOpacity: 0.8, weight: 1,
        }).bindTooltip(`FIRMS ${p.acq_date || ''}`).addTo(g)
      })
      g.addTo(map)
      lyr.current.fire = g
    }
  }, [JSON.stringify(firepoints), showFire])

  // recommendations: fire head, suppression zones, firebreaks (GeoJSON lon,lat)
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (lyr.current.rec) { map.removeLayer(lyr.current.rec); lyr.current.rec = null }
    if (!showRec || !recommendation) return
    const t = makeT(lang)
    const g = L.layerGroup()
    for (const f of recommendation.features || []) {
      const k = f.properties?.kind
      const c = f.geometry.coordinates
      if (k === 'fire_head') {
        L.marker([c[1], c[0]], { icon: L.divIcon({ className: '', html: '🎯', iconSize: [26, 26], iconAnchor: [13, 13] }) })
          .bindTooltip(t('legFireHead')).addTo(g)
      } else if (k === 'suppression_zone') {
        // small numbered badge (no permanent label so it doesn't cover the heatmap);
        // plain details appear on hover/tap.
        const p = f.properties.burn_prob
        const near = nearestAsset(c[0], c[1], assets)
        const detail = `${t('order')} ${f.properties.priority}` +
          (near ? ` · ${t('nearComm')} ${near.name} ~${r1(near.km)} กม.` : '') +
          ` · ${t('chance')} ${pct0(p)}% (${chanceWord(p, lang)})`
        L.marker([c[1], c[0]], {
          icon: L.divIcon({ className: 'zone-badge', html: `<span>${f.properties.priority}</span>`, iconSize: [22, 22], iconAnchor: [11, 11] }),
        }).bindTooltip(detail).addTo(g)
      } else if (k === 'firebreak_suggested') {
        L.polyline(c.map(([lon, lat]) => [lat, lon]), { color: '#22d3ee', weight: 5, dashArray: '10 7' })
          .bindTooltip(t('legFirebreak')).addTo(g)
      } else if (k === 'firebreak_natural') {
        const water = L.layerGroup()
        c.forEach(([lon, lat]) =>
          L.circleMarker([lat, lon], { radius: 3, color: '#38bdf8', fillColor: '#38bdf8', fillOpacity: 0.85, weight: 1 }).addTo(water))
        water.bindTooltip(t('legWater')).addTo(g)
      }
    }
    g.addTo(map)
    lyr.current.rec = g
  }, [JSON.stringify(recommendation), showRec, lang])

  return <div id="map" ref={elRef} />
}
