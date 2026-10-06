# Design — Campus Customs "Varsity Press" (Problem 10)

## Concept

Campus Customs is a family screen-print shop that moved into the old York Square Cinema on Broadway. The redesign turns those two facts into the site's visual language:

- **Varsity Press (everywhere):** Yale-blue ink on paper white, halftone dot textures, a slightly off-register "print shadow", varsity lettering, and photos that are *printed* onto the page.
- **The Marquee (once, on Home):** a movie-theater sign with chasing yellow bulbs that reads **NOW PRINTING · WEAR THE BLUE**.

The style tells the shop's story without a paragraph of text, which makes it distinct from a generic campus store.

## What changed, and why it keeps shoppers longer and helps them buy

| Area | What changed | Why it helps shoppers stay and buy |
|---|---|---|
| **Fonts** | Oswald (condensed varsity display) for headings, prices, tabs and buttons; Fraunces (warm serif) for story lines and product descriptions; Inter for body and UI. All three are self-hosted through npm (`@fontsource-variable/*`), so the site renders identically offline and on any grader machine. | Condensed caps read as athletic wear and fit long product names on one line. Each typeface has one job, so shoppers learn instantly what is a headline, what is a story and what is a control. Less reading effort means more browsing. |
| **Colors** | One Yale-blue ink scale (ink → Yale Blue → light blue → tint) on white and "paper" cream. A single accent, marquee yellow, is reserved for things that should be noticed: bulbs, the price tag, the "See all" ticket, primary-button shadows. | Keeps the brand rule (White + Yale Blue) while giving the eye a clear path. When yellow only marks prices and next steps, it acts as a signpost toward purchase, not decoration. |
| **Hierarchy** | Fixed type scale. Uppercase display for section titles and serif for the emotional line ("Mean it."). Sections alternate white / paper / halftone blue for rhythm. Price and stock always appear in the same place, size and color on every card and page. | Shoppers scan rather than read. A predictable layout lets them compare products quickly and find price and stock without hunting, which cuts the moment where people give up. |
| **Motion** | **Squeegee reveal:** each product photo is wiped onto its card by a blue squeegee the first time it scrolls into view. **Marquee bulbs** chase. A **ticker** strip ("Printed in-house · 102 styles · XS to XXL …") scrolls under the hero. Tabs slide their underline, filter chips pop, cards lift with a print shadow, and Dan the bulldog bobs and tilts his head while thinking. All motion is CSS, short (≤ 0.75 s) and fully off when the visitor has "reduce motion" on. | Small, purposeful motion rewards scrolling, so every new row "prints" in, which invites the next scroll and lengthens sessions. Feedback motion (chip pop, tab slide) confirms each click and makes filtering feel responsive, so shoppers keep refining instead of leaving. |
| **Product presentation** | White-background photos (Problem 9) on cards with an off-register hover shadow. **Sizes in stock appear on hover**, sold-out sizes struck through. The product page has a **zoom-on-hover photo**, a rotated **"Printed on Broadway" stamp**, a yellow price tag, **ticket-stub size chips**, a "Going fast: only 2 in XXL" note, and **"Also in this design"** (the same print as another garment, e.g. the hoodie's crewneck). | Shoppers decide faster when they can see stock before clicking and inspect the print up close. Honest scarcity ("only 2 left") is a real reason to buy now, and it comes straight from the database. "Also in this design" turns one product view into a cross-sell. |
| **Chat feel — "Ask Dan"** | The assistant became **Dan**, the shop bulldog: a launcher pill with Dan and "Ask Dan", a panel that opens with an ink-spread animation, halftone header, white speech bubbles with print shadows, **price-tag product cards**, a yellow **ticket** for "See all N", and a typing state "Dan is checking the shelves…" with Dan tilting his head. **Starter questions change with the page** (on a product page: "Is my size in stock?", "Other colors?"). Product pages have **Ask Dan buttons** that open the chat and ask about that product in one click. | A named character with a face makes help feel approachable, so more shoppers ask instead of bouncing. Page-aware prompts and one-click questions remove the "what do I type?" moment. Answers lead straight to cards and filtered pages, so the conversation ends in a product, not a dead end. |
| **The Marquee hero** | The Home hero is a lit theater marquee with chasing bulbs, the line "Mean it." in serif italic, a bobbing Handsome Dan, and a tilted yellow ticker beneath. | A memorable first screen sets the shop apart within seconds and ties the brand to a place (57 Broadway). Visitors who feel a store's personality are more likely to explore than visitors who see a generic template. |

## Guardrails

- **Nothing about the data changed.** The redesign is presentation only; prices, stock and the chat's database checks are untouched (regression tests 30/30; filter accuracy check across 8,400 combinations still exact).
- **Accessibility:** text keeps strong contrast (ink and Yale Blue on white, white on Yale Blue). Focus rings are visible, decorative SVGs are hidden from screen readers, and "reduce motion" disables every animation and the photo reveal.
- **Performance:** no animation library. Motion is CSS plus one small IntersectionObserver hook. Fonts are bundled, so there is no third-party font request.
- **Robustness:** if a browser lacks IntersectionObserver, photos are shown immediately rather than waiting for a reveal.
- **Branding rule kept:** White + Yale Blue throughout, with the `YALE SOM - Yonghyuk Choi` bands at the top and bottom of every page.

## Where to see it

Home (marquee hero, ticker, print-shadow cards, collection tiles, bulldog family) · Products (sliding tabs, size preview on hover, squeegee reveal) · any product page (zoom, stamp, ticket sizes, Also in this design, Ask Dan buttons) · the **Ask Dan** chat in the corner on every page.
