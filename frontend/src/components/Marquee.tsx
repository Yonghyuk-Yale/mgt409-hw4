/** The Home hero sign: Campus Customs moved into the old York Square Cinema, so the shop's
 *  first screen is a movie-theater marquee with chasing yellow bulbs. */

const TOP_BULBS = 22
const SIDE_BULBS = 6

function Bulbs({ count, edge }: { count: number; edge: 'top' | 'bottom' | 'left' | 'right' }) {
  return (
    <span className={`marquee-bulbs marquee-bulbs-${edge}`} aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <span key={i} className="bulb" style={{ animationDelay: `${(i % 3) * 0.35}s` }} />
      ))}
    </span>
  )
}

export default function Marquee({ kicker, title }: { kicker: string; title: string }) {
  return (
    <div className="marquee">
      <Bulbs count={TOP_BULBS} edge="top" />
      <Bulbs count={TOP_BULBS} edge="bottom" />
      <Bulbs count={SIDE_BULBS} edge="left" />
      <Bulbs count={SIDE_BULBS} edge="right" />
      <p className="marquee-kicker">{kicker}</p>
      <p className="marquee-title">{title}</p>
    </div>
  )
}
