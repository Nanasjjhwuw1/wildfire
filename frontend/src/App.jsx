import { useEffect, useRef, useState } from 'react'
import MapView from './components/MapView.jsx'
import Legend from './components/Legend.jsx'
import * as api from './api.js'
import {
  makeT, r0, r1, pct0, dangerInfo, windPhrase, windWord, drynessWord,
  chanceWord, dirWord, dirArrow, bearingDeg, nearestAsset, formatDuration,
} from './i18n.js'

function Info({ text }) {
  return <span className="info" tabIndex={0} title={text} aria-label={text}>i</span>
}

function RiskLegend({ t }) {
  return (
    <div className="risk-legend">
      <div className="rl-cap">{t('colorScale')}</div>
      <div className="rl-bar" />
      <div className="rl-labels"><span>{t('riskLess')}</span><span>{t('riskMore')}</span></div>
    </div>
  )
}

function Welcome({ t, lang, setLang, onStart }) {
  return (
    <div className="welcome">
      <div className="welcome-card">
        <button className="lang-btn welcome-lang" onClick={() => setLang(lang === 'th' ? 'en' : 'th')}>{lang === 'th' ? 'EN' : 'ไทย'}</button>
        <div className="welcome-icon">🔥</div>
        <h1>{t('welcomeTitle')}</h1>
        <p>{t('welcomeDesc')}</p>
        <div className="welcome-legend">
          <span><b className="sw" style={{ background: '#1f9d57' }} /> {t('riskLow')}</span>
          <span><b className="sw" style={{ background: '#e8b021' }} /> {t('riskMed')}</span>
          <span><b className="sw" style={{ background: '#d83a2e' }} /> {t('riskHigh')}</span>
        </div>
        <ol className="welcome-steps">
          <li><span>1</span> {t('wStep1')}</li>
          <li><span>2</span> {t('wStep2')}</li>
          <li><span>3</span> {t('wStep3')}</li>
        </ol>
        <button className="btn big" onClick={onStart}>{t('start')} →</button>
      </div>
    </div>
  )
}

async function retry(fn, tries = 5, delay = 700) {
  let last
  for (let i = 0; i < tries; i++) {
    try { return await fn() } catch (e) { last = e; await new Promise((r) => setTimeout(r, delay)) }
  }
  throw last
}

export default function App() {
  const [lang, setLang] = useState('th')
  const [deep, setDeep] = useState(false)
  const [theme, setTheme] = useState('dark')
  const [started, setStarted] = useState(false)
  const [simpleMode, setSimpleMode] = useState(true)
  const t = makeT(lang)

  const [area, setArea] = useState(null)
  const [risk, setRisk] = useState(null)
  const [sim, setSim] = useState(null)
  const [rec, setRec] = useState(null)
  const [firepoints, setFirepoints] = useState([])
  const [riskMl, setRiskMl] = useState(null)
  const [ignition, setIgnition] = useState(null)
  const [error, setError] = useState(null)
  const [loadingArea, setLoadingArea] = useState(true)
  const [simulating, setSimulating] = useState(false)

  const [windSpeed, setWindSpeed] = useState(6)
  const [windDir, setWindDir] = useState(225)
  const [dryness, setDryness] = useState(0.9)
  const [nRuns, setNRuns] = useState(30)
  const [ros, setRos] = useState(50)

  const [baseLayer, setBaseLayer] = useState('fwi')
  const [showBurn, setShowBurn] = useState(true)
  const [showRec, setShowRec] = useState(true)
  const [showFire, setShowFire] = useState(false)
  const [national, setNational] = useState(null)
  const [showNational, setShowNational] = useState(false)

  const [playing, setPlaying] = useState(false)
  const [frameIdx, setFrameIdx] = useState(0)
  const timer = useRef(null)
  const didAuto = useRef(false)

  useEffect(() => {
    document.documentElement.classList.toggle('light', theme === 'light')
  }, [theme])

  useEffect(() => {
    (async () => {
      try {
        const [a, r] = await retry(() => Promise.all([api.getArea(), api.getRisk()]))
        setArea(a)
        setRisk(r)
        let ws = windSpeed, wd = windDir
        if (a.weather) {
          if (typeof a.weather.wind_speed === 'number') { ws = Math.round(a.weather.wind_speed * 10) / 10; setWindSpeed(ws) }
          if (typeof a.weather.wind_dir === 'number') { wd = Math.round(a.weather.wind_dir); setWindDir(wd) }
        }
        api.getFirepoints().then((f) => setFirepoints(f.points || [])).catch(() => {})
        retry(() => api.getRiskMl(), 3, 900).then(setRiskMl).catch(() => setRiskMl(null))
        if (!didAuto.current && a.bounds) {
          didAuto.current = true
          const [[s, w], [n, e]] = a.bounds
          const lat = (s + n) / 2, lon = (w + e) / 2
          setIgnition({ lat, lon })
          runSimulation(lat, lon, { wind_speed: ws, wind_direction: wd, fuel_dryness: 0.9 })
        }
      } catch (e) {
        setError(`${t('loadFailed')}: ${e.message}`)
      } finally {
        setLoadingArea(false)
      }
    })()
  }, [])

  useEffect(() => {
    clearInterval(timer.current)
    if (playing && sim && sim.frames.length) {
      timer.current = setInterval(() => {
        setFrameIdx((i) => { if (i >= sim.frames.length - 1) { setPlaying(false); return i } return i + 1 })
      }, 120)
    }
    return () => clearInterval(timer.current)
  }, [playing, sim])

  async function runSimulation(lat, lon, override = {}) {
    setSimulating(true)
    setError(null)
    setPlaying(false)
    try {
      const res = await api.simulate({
        lat, lon,
        wind_speed: override.wind_speed ?? windSpeed,
        wind_direction: override.wind_direction ?? windDir,
        fuel_dryness: override.fuel_dryness ?? dryness,
        n_runs: override.n_runs ?? nRuns,
        n_steps: 60,
      })
      setSim(res)
      setFrameIdx(res.frames.length - 1)
      setShowBurn(true)
      setRec(null)
      api.recommend(res.sim_id).then(setRec).catch(() => setRec(null))
    } catch (e) {
      setError(`${t('simFailed')}: ${e.message}`)
    } finally {
      setSimulating(false)
    }
  }

  function handleClick(lat, lon) {
    const b = area?.bounds
    if (b) {
      const [[s, w], [n, e]] = b
      if (lat < s || lat > n || lon < w || lon > e) { setError(t('outsideMsg')); return }
    }
    setError(null)
    setIgnition({ lat, lon })
    runSimulation(lat, lon)
  }

  function reset() {
    setSim(null); setRec(null); setIgnition(null); setError(null); setPlaying(false); setFrameIdx(0)
  }

  async function toggleNational() {
    if (!showNational && !national) {
      try { setNational(await api.getNational()) }
      catch { setError(t('nationalBuilding')); return }
    }
    setShowNational((v) => !v)
  }

  const burnImage = sim && sim.frames.length ? sim.frames[Math.min(frameIdx, sim.frames.length - 1)] : null
  const wx = area?.weather
  const danger = risk ? dangerInfo(risk.danger_class, lang) : null
  const activeStep = sim ? 3 : 2
  const cellM = area?.grid?.cell_size_m || 100
  const totalMin = sim ? (sim.n_steps * cellM) / ros : 0
  const frameMin = (idx) => (sim && sim.frames.length ? (totalMin * (idx + 1)) / sim.frames.length : 0)

  function summarySentence() {
    if (!sim || !rec) return null
    const head = rec.summary.fire_head
    const deg = bearingDeg(sim.ignition.lat, sim.ignition.lon, head[1], head[0])
    const dir = dirWord(deg, lang), arrow = dirArrow(deg)
    const x = Math.round(sim.stats.burned_fraction * 100)
    const n = rec.summary.assets_threatened
    const dur = formatDuration(totalMin, lang)
    if (lang === 'th') {
      const hit = n > 0 ? `กระทบ ${n} ชุมชน` : 'ยังไม่กระทบชุมชนในรายการ'
      return `ถ้าไฟเริ่มตรงนี้ในสภาพอากาศที่ตั้งไว้ ไฟจะลามไปทาง${dir} ${arrow} ครอบคลุมราว ${x}% ของพื้นที่ภายในเวลาประมาณ ${dur} ${hit}` +
        (n > 0 ? ' — ควรเร่งส่งทีมไปสกัดที่จุดสีส้มตามลำดับ' : '')
    }
    const hit = n > 0 ? `threatening ${n} communit${n > 1 ? 'ies' : 'y'}` : 'no listed community hit yet'
    return `If a fire starts here in the set conditions, it spreads ${dir} ${arrow}, covering ~${x}% of the area in about ${dur}, ${hit}` +
      (n > 0 ? ' — send crews to the orange points in order.' : '')
  }

  if (!started) return <Welcome t={t} lang={lang} setLang={setLang} onStart={() => setStarted(true)} />

  return (
    <div className={`app ${simpleMode ? 'simple-app' : ''}`}>
      <header className="topbar">
        <div className="brand">🔥 {t('appTitle')} <span className="brand-area">· {t('area')}</span></div>
        {!simpleMode && (
          <div className="steps">
            <span className={`step ${activeStep === 1 ? 'active' : ''}`}>1 {t('stepWeather')}</span>
            <span className={`step ${activeStep === 2 ? 'active' : ''}`}>2 {t('stepIgnite')}</span>
            <span className={`step ${activeStep === 3 ? 'active' : ''}`}>3 {t('stepResult')}</span>
          </div>
        )}
        {simpleMode && <div className="spacer" />}
        <div className="topctrl">
          <button className="lang-btn" onClick={toggleNational}>🗺️ {showNational ? t('localView') : t('national')}</button>
          <button className="lang-btn" onClick={() => setSimpleMode(!simpleMode)}>{simpleMode ? `⚙️ ${t('seeDetail')}` : t('simpleBack')}</button>
          {!simpleMode && <label className="deep-toggle"><input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} /> {t('deep')}</label>}
          {!simpleMode && <button className="theme-btn" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="theme">{theme === 'dark' ? '☀️' : '🌙'}</button>}
          <button className="lang-btn" onClick={() => setLang(lang === 'th' ? 'en' : 'th')}>{lang === 'th' ? 'EN' : 'ไทย'}</button>
        </div>
      </header>

      <div className="main">
        <div className="map-wrap">
          <MapView
            bounds={area?.bounds} riskImage={risk?.image} burnImage={burnImage}
            showRisk={baseLayer === 'fwi'} showBurn={showBurn} ignition={ignition}
            assets={area?.assets || []} firepoints={firepoints} showFire={showFire}
            recommendation={rec} showRec={showRec} lang={lang} onClick={handleClick}
            riskMlImage={riskMl?.image} showRiskMl={baseLayer === 'ai' && !!riskMl}
            nationalImage={national?.image} nationalBounds={national?.bounds} showNational={showNational}
          />
          {!ignition && !showNational && <div className="map-hint">{t('mapHintFirst')}</div>}
          <div className="north-arrow" title="North"><b>↑</b>N</div>
          {(simulating || loadingArea) && <div className="spinner-overlay"><div className="spinner" /></div>}
        </div>

        <aside className="sidebar">
          {error && <div className="error">{error}</div>}

          {simpleMode ? (
            <div className="simple">
              {showNational ? (
                <>
                  <div className="big-danger">
                    <div className="bd-label">{t('natTitle')}</div>
                    <div className="nat-note">{t('natNote')}</div>
                  </div>
                  <RiskLegend t={t} />
                </>
              ) : (
                <>
                  {danger && (
                    <div className="big-danger">
                      <div className="bd-label">{t('todayRisk')}</div>
                      <div className="bd-badge" style={{ background: danger.color }}>{danger.emoji} {danger.label}</div>
                    </div>
                  )}
                  {!sim && <div className="tap-hint">{t('tapToSim')}</div>}
                  {sim && (
                    <div className="result-card">
                      <div className="example-tag">{t('exampleNote')}</div>
                      {summarySentence() && <div className="summary big">{summarySentence()}</div>}
                      {rec && rec.summary.assets_threatened > 0 && (
                        <div className="big-line">🚒 {t('sendCrews')} {rec.summary.n_suppression_zones} จุด</div>
                      )}
                      <div className="btn-row">
                        <button className="btn secondary" onClick={() => { setFrameIdx(0); setPlaying(true) }}>{t('btnPlay')}</button>
                        <button className="btn secondary" onClick={reset}>{t('newFire')}</button>
                      </div>
                    </div>
                  )}
                  <RiskLegend t={t} />
                </>
              )}
              <button className="btn" onClick={toggleNational}>🗺️ {showNational ? t('localView') : t('national')}</button>
              <button className="btn secondary" onClick={() => setSimpleMode(false)}>⚙️ {t('seeDetail')}</button>
            </div>
          ) : (
            <>
              <div className="section now">
                <h2>🟢 {t('secNow')}</h2>
                {wx && danger ? (
                  <>
                    <div className="danger-line">
                      <span>{t('dangerToday')} <Info text={t('infoDanger')} /></span>
                      <span className="danger-badge" style={{ background: danger.color }}>{danger.emoji} {danger.label}</span>
                    </div>
                    <div className="stat-row"><span>{t('air')}</span><b>{r0(wx.temp)}°C · {t('humidity')} {r0(wx.rh)}%</b></div>
                    <div className="stat-row"><span>{t('rain24')}</span><b>{r1(wx.rain_24h)} mm</b></div>
                    <div className="stat-row"><span>{t('windLabel')}</span><b>{windPhrase(wx.wind_speed, wx.wind_dir, lang)}</b></div>
                    {deep && <>
                      <div className="stat-row deep"><span>{t('indices')} <Info text={t('infoFwi')} /></span><b>{risk.ffmc} / {risk.isi}</b></div>
                      <div className="stat-row deep"><span>{t('windLabel')} (°)</span><b>{r1(wx.wind_speed)} m/s @ {r1(wx.wind_dir)}°</b></div>
                      <div className="stat-row deep"><span>{t('source')}</span><b>{wx.source}</b></div>
                    </>}
                  </>
                ) : <div className="sub">…</div>}
              </div>

              <div className="section">
                <h2>🎚️ {t('secSettings')}</h2>
                <div className="field">
                  <label>{t('dryness')} <Info text={t('infoDryness')} /> <span>{drynessWord(dryness * 100, lang)} ({Math.round(dryness * 100)}%)</span></label>
                  <input type="range" min="0.05" max="1" step="0.05" value={dryness} onChange={(e) => setDryness(+e.target.value)} />
                  <div className="ends"><span>{t('drynessLo')}</span><span>{t('drynessHi')}</span></div>
                </div>
                <div className="field">
                  <label>{t('windStrength')} <span>{windWord(windSpeed, lang)}{deep ? ` (${r1(windSpeed)} m/s)` : ''}</span></label>
                  <input type="range" min="0" max="30" step="0.5" value={windSpeed} onChange={(e) => setWindSpeed(+e.target.value)} />
                  <div className="ends"><span>{t('weak')}</span><span>{t('strong')}</span></div>
                </div>
                <div className="field">
                  <label>{t('windDir')} <span>{dirWord(windDir, lang)} {dirArrow(windDir + 180)}{deep ? ` (${windDir}°)` : ''}</span></label>
                  <input type="range" min="0" max="360" step="5" value={windDir} onChange={(e) => setWindDir(+e.target.value)} />
                </div>
                {deep && (
                  <>
                    <div className="field deep">
                      <label>{t('mcRuns')} <span>{nRuns}</span></label>
                      <input type="range" min="5" max="60" step="5" value={nRuns} onChange={(e) => setNRuns(+e.target.value)} />
                    </div>
                    <div className="field deep">
                      <label>{t('assumedRos')} <span>{ros} m/min</span></label>
                      <input type="range" min="10" max="200" step="5" value={ros} onChange={(e) => setRos(+e.target.value)} />
                    </div>
                  </>
                )}
                <button className="btn" disabled={!ignition || simulating} onClick={() => ignition && runSimulation(ignition.lat, ignition.lon)}>
                  {simulating ? '…' : t('btnRerun')}
                </button>
              </div>

              {sim && (
                <div className="section result">
                  <h2>🔥 {t('secResult')}</h2>
                  {summarySentence() && <div className="summary">{summarySentence()}</div>}
                  <div className="stat-row"><span>{t('ignitionPoint')}</span><b>{r1(sim.ignition.lat)}, {r1(sim.ignition.lon)}</b></div>
                  <div className="stat-row"><span>{t('spreadTimeTotal')}</span><b>~{formatDuration(totalMin, lang)} ({t('approx')})</b></div>
                  <div className="stat-row"><span>{t('windUsed')}</span><b>{windWord(sim.wind.speed, lang)} {dirWord(sim.wind.direction, lang)} ({sim.wind.source === 'user' ? t('youSet') : t('liveVal')})</b></div>
                  <div className="btn-row" style={{ marginTop: 8 }}>
                    <button className="btn secondary" onClick={() => { setFrameIdx(0); setPlaying(true) }}>{t('btnPlay')}</button>
                    <button className="btn secondary" onClick={() => setPlaying(false)}>{t('btnPause')}</button>
                    <button className="btn secondary tiny" onClick={reset}>{t('reset')}</button>
                  </div>
                  <label className="mini">{t('spreadStage')}</label>
                  <input type="range" min="0" max={sim.frames.length - 1} value={Math.min(frameIdx, sim.frames.length - 1)}
                         onChange={(e) => { setPlaying(false); setFrameIdx(+e.target.value) }} style={{ width: '100%' }} />
                  <div className="sub" style={{ padding: 0 }}>
                    {Math.min(frameIdx, sim.frames.length - 1) + 1} / {sim.frames.length} · {t('timeApprox')} ~{formatDuration(frameMin(Math.min(frameIdx, sim.frames.length - 1)), lang)}
                  </div>
                  {deep && <>
                    <div className="stat-row deep"><span>{t('rawMaxProb')}</span><b>{sim.stats.max_burn_prob}</b></div>
                    <div className="stat-row deep"><span>{t('frames')}</span><b>{sim.frames.length}</b></div>
                  </>}
                </div>
              )}

              {rec && (
                <div className="section">
                  <h2>🚒 {t('secAdvice')}</h2>
                  <div className="stat-row"><span>{t('assetsThreatened')}</span><b>{rec.summary.assets_threatened} {t('places')}</b></div>
                  <div className="stat-row"><span>{t('suppressPoints')} <Info text={t('infoBurn')} /></span><b>{rec.summary.n_suppression_zones} {t('points')}</b></div>
                  <ul className="rec-list">
                    {rec.features.filter((f) => f.properties.kind === 'suppression_zone').map((f) => {
                      const [lon, latv] = f.geometry.coordinates
                      const near = nearestAsset(lon, latv, area?.assets)
                      const p = f.properties.burn_prob
                      return (
                        <li key={`z${f.properties.priority}`}>
                          <span className="zbadge">{f.properties.priority}</span>
                          {near ? `${t('nearComm')} ${near.name} ~${r1(near.km)} กม. · ` : ''}
                          {t('chance')} {pct0(p)}% ({chanceWord(p, lang)})
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}

              <div className="section">
                <h2>🗺️ {t('secLayers')}</h2>
                <div className="sub" style={{ padding: '0 0 6px' }}>{t('layerBase')}</div>
                <div className="radio-row">
                  <label><input type="radio" name="base" checked={baseLayer === 'none'} onChange={() => setBaseLayer('none')} /> {t('layerNone')}</label>
                  <label><input type="radio" name="base" checked={baseLayer === 'fwi'} onChange={() => setBaseLayer('fwi')} /> {t('layerFwi')}</label>
                  <label>
                    <input type="radio" name="base" disabled={!riskMl} checked={baseLayer === 'ai'} onChange={() => setBaseLayer('ai')} />
                    🤖 {t('layerRiskMl')} {riskMl ? '' : `(${t('notTrained')})`}
                  </label>
                </div>
                {deep && riskMl && (
                  <div className="stat-row deep"><span>{t('mlAuc')} <Info text={t('infoAuc')} /></span><b>{riskMl.metrics?.auc} · {riskMl.metrics?.n_pos}</b></div>
                )}
                <div className="toggles" style={{ marginTop: 8 }}>
                  <label className="toggle"><input type="checkbox" checked={showBurn} onChange={(e) => setShowBurn(e.target.checked)} /> {t('layerBurn')}</label>
                  <label className="toggle"><input type="checkbox" checked={showRec} onChange={(e) => setShowRec(e.target.checked)} /> {t('layerPlan')}</label>
                  <label className="toggle">
                    <input type="checkbox" checked={showFire} disabled={!firepoints.length} onChange={(e) => setShowFire(e.target.checked)} />
                    {t('layerFirms')} {firepoints.length ? `(${firepoints.length})` : `(${t('none')})`}
                  </label>
                </div>
              </div>

              <div className="section">
                <h2>📖 {t('secLegend')}</h2>
                <Legend t={t} showRisk={baseLayer !== 'none'} showBurn={showBurn} />
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
