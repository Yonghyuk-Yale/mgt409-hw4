import { Link } from 'react-router-dom'
import { BULLDOG_COATS } from '../bulldog'
import YH_Bulldog from '../components/YH_Bulldog'

const VALUES = [
  {
    title: 'Made here, not just sold here',
    text: 'Screen printing and embroidery happen in-house at 57 Broadway. When we put a crest on a chest, the press it came off is in the next room.',
  },
  {
    title: 'Official, not lookalike',
    text: 'Licensed Yale merchandise for the people who actually walk these streets: students, alumni, staff, and everyone who visits them.',
  },
  {
    title: 'Honest about the shelf',
    text: "Prices are what you see. Stock is counted size by size. If your size is gone, we'll tell you, and point you to one that isn't.",
  },
]

export default function About() {
  return (
    <>
      <section className="page-hero">
        <p className="eyebrow">About Us</p>
        <h1>Half a century on Broadway. No plans to leave.</h1>
      </section>

      <section className="story">
        <div className="story-text">
          <h2>A family shop that never moved out</h2>
          <p>
            Campus Customs opened in 1975 as a small Yale memorabilia shop across the street from
            campus. It has been a family business ever since: a founder who learned retail on
            Broadway as a teenager, and two sons who picked up the ink and the keys from there.
          </p>
          <p>
            In the 1990s we started printing our own shirts. When the York Square Cinema next door
            went dark in 2005, we spent close to two years turning a movie theater into a print shop
            and a store. The projector is gone. The crowds still show up, now for sweatshirts
            instead of showtimes.
          </p>
          <p>
            Some of our team have been here for close to twenty years. We don't advertise that as a
            perk. It's just how a family shop works.
          </p>
        </div>
        <aside className="story-facts">
          <div>
            <strong>1975</strong>
            <span>First day on Broadway</span>
          </div>
          <div>
            <strong>1990s</strong>
            <span>Started printing in-house</span>
          </div>
          <div>
            <strong>2007</strong>
            <span>The old cinema becomes our shop</span>
          </div>
        </aside>
      </section>

      <section className="values">
        {VALUES.map((value) => (
          <article key={value.title} className="value-card">
            <h3>{value.title}</h3>
            <p>{value.text}</p>
          </article>
        ))}
      </section>

      <section className="visit">
        <YH_Bulldog furColor={BULLDOG_COATS.fawn} size={84} className="hero-dog-center" />
        <h2>Come by 57 Broadway</h2>
        <p>Between classes, before the game, or the day the acceptance letter arrives.</p>
        <Link to="/products" className="btn btn-blue">
          Or shop from here
        </Link>
      </section>
    </>
  )
}
