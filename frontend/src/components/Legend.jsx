export default function Legend({ t, showRisk, showBurn }) {
  return (
    <div className="legend">
      {(showBurn || showRisk) && (
        <>
          <div className="bar burn" />
          <div className="scale"><span>{t('chanceLow')}</span><span>{t('chanceHigh')}</span></div>
          <div className="cap">{t('chance')}</div>
        </>
      )}
      <div className="row"><span className="sym">🔥</span> {t('legIgnition')}</div>
      <div className="row"><span className="sym">🎯</span> {t('legFireHead')}</div>
      <div className="row"><span className="dot orange" /> {t('legSuppress')}</div>
      <div className="row"><span className="line cyan" /> {t('legFirebreak')}</div>
      <div className="row"><span className="dot blue" /> {t('legWater')}</div>
      <div className="row"><span className="sym">🏠</span> {t('legCommunity')}</div>
    </div>
  )
}
