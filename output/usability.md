# Usability Improvements — Campus Customs (Problem 9)

Using the website and chatbot ourselves, we picked four places where shoppers got stuck and fixed them: two front-end and two back-end/agent improvements. Each one is described in the same order: (1) what changed, (2) why it helps shoppers, (3) why it helps the shop as a business, and (4) how it was verified.

| # | Area | Improvement | Where to see it |
|---|---|---|---|
| 1 | Front end | Category tabs + "Shop for" collections + filters (price, color, **my size in stock**) + search and sort | Products page; "Shop for" tiles on Home |
| 2 | Front end | Every product photo on a consistent white background | All product cards, product pages, chat cards |
| 3 | Back end / agent | "See all N" button from the chat to a filtered Products page | Ask the chat "What hoodies do you have?" |
| 4 | Back end / agent | A tool that finds in-stock alternatives when the shopper's size is sold out | On a product page, ask the chat "Do you have this in XS?" |
| + | Brand | Bulldog mascot (around Home, empty results, 404, chat avatar, footer) | Whole site |

---

## 1. Category tabs + collections + filters (front end)

**What changed**
- **Category tabs** at the top of the Products page: All, T-Shirts, Long-Sleeve, Crewnecks & Sweatshirts, Hoodies, Full-Zip Hoodies, Quarter-Zips, Jackets. Each tab shows its product count.
- **"Shop for" collections**: Family (12), Residential Colleges (19), Graduate & Professional Schools (13), Sports (36), Yale Classics (22). Products are classified by name, so all 102 fall into exactly one collection.
- **Filter panel**: price range (Under $40 / $40–60 / $60–80 / $80+), body color (Navy, Gray, Cream & White, Coral), and **"My size is in stock"** (XS–XXL). On top of that, a search box (searches 300 ms after typing stops) and sorting (featured, price low/high, name).
- Active filters appear as removable chips, and "Clear all filters" removes them in one click. Each option shows how many products would remain if it were picked, and options that would leave 0 are greyed out.
- **Every filter lives in the page URL** (e.g. `/products?collection=family&category=hoodies&size=XXL`), so refresh, back, and sharing a link all work. Improvement 3 (the chatbot link) uses the same URLs.
- **Five "Who are we dressing today?" tiles** on Home open the Products page with that collection already applied.
- On phones, the filters fold away behind a "Filters" button.

**Why it helps shoppers**
- Scanning 102 products in one long list becomes a few clicks. For example, Family → Hoodies → XXL leaves 5.
- **The "my size is in stock" filter is the key.** 145 of the 612 size-level stock rows (24%) are sold out, so shoppers often opened a product they liked only to find their size gone. Now they see only what they can actually buy, and cards carry an "XXL in stock" badge.
- Gift buyers (family) and people showing their affiliation (colleges, schools, sports) go straight to their own section.

**Why it helps the business**
- Less time searching means fewer drop-offs and more purchases, and disappointment over sold-out sizes is filtered out up front.
- Strong sellers such as the Family collection are surfaced on the Home page, opening cross-selling (a student plus a gift for their parents).
- Filter URLs double as campaign links for email or social media (e.g. "Parents' Weekend: `/products?collection=family`").

**How it works** — `GET /api/products/browse` (backend `catalogue.browse()`) does the filtering and per-option counts in one place; the front end passes the URL's conditions through and draws the result. Because there is only one filter implementation, the page and the chatbot (improvement 3) always show the same numbers.

**What was verified** — **All 8,400 combinations** (8 categories × 6 collections × 5 colors × 7 sizes × 5 prices) were compared against results computed separately from the raw DB, with **0 mismatches**. "Number next to an option = number of results after clicking it" also had 0 mismatches on a sample of combinations. In the browser: desktop and phone (375px) layouts, the empty-results screen, and sharing URLs.

---

## 2. White background for every product photo (front end)

**What changed** — Of the 102 original photos, only 28 had a white background; 46 sat on a black square and 28 had black side bars. Now every photo on the site (list, product page, chat cards) appears on white.

**Why it helps shoppers**
- The product, not the patchy background, is what stands out. In particular, navy and charcoal garments that disappeared into black backgrounds now show their shape.
- With photos in the same conditions, colors and designs are easy to compare side by side.

**Why it helps the business**
- Tidy product photography is directly tied to an online store's credibility. Uneven photos make an official store look like a second-hand marketplace.
- The existing photos are reused as they are, with no reshoot or editing (zero cost).

**How it works**
- The original photos are not in the repository and are not modified (assignment rule). Instead, the backend transforms each photo as it serves it (`backend/images.py`, Pillow).
- Starting from the **edge of the photo, only connected pure-black areas** are painted white. Dark parts inside a garment aren't connected to the edge, so they are left untouched.
- A first threshold of 34 also erased the edges of three very dark navy garments (Basic Hoodie, Boola Boola tee, Football tee). Measurements showed the background is exactly 0–3 while garment shadows are 10–30, so the threshold was set to **8**.
- Results are made once and cached in `data/products_white/` (0.2 s per photo on average; all 102 are prepared in the background when the server starts). If processing fails, the original photo is served instead.
- File names that aren't in the catalogue are refused with 404.
- Photo URLs carry the processing version (`…jpg?v=v2`). With an unchanged URL, a browser keeps showing the black-background copy it cached earlier; this actually happened in a browser that had already visited the site. When the processing changes, the version changes and every browser fetches the new photo.

**What was verified** — Before/after images of all 102 photos were inspected side by side: 0 damaged garments and 0 photos with black background left (the 2 with dark edges are garments that extend past the photo frame).

---

## 3. "See all N" from the chat to a filtered Products page (back end / agent)

**What changed**
- Chat answers show at most 6 cards, so "what hoodies do you have?" matched 25 but ended after showing 6.
- A new agent tool, `make_browse_link`, turns the shopper's request into filters (category, collection, color, size, price), **counts how many products those filters actually return**, and makes a link.
- Under the chat answer, a **"See all 25 hoodies →"** button opens the Products page with those filters. On wide screens the chat stays open so the conversation can continue.

**Why it helps shoppers**
- Browsing that starts in a conversation no longer hits a dead end. Say "gray crewnecks under $60" and you land on the full list with those conditions applied, with no need to pick each filter again.

**Why it helps the business**
- The chatbot goes from help desk to **store guide**: one question exposes the whole matching range, raising purchase opportunities from 6 products to dozens.
- Demand that arrives through the chat now has a path into browsing the site.

**Accuracy safeguards**
- The number on the button is counted by **the same function** as the Products page (`catalogue.browse`).
- If the agent returns a URL it did not create with `make_browse_link` in this turn, the server rejects it (output validator).
- Prompt rule: when giving a link, quote the link's own count.

**What was verified (real gpt-6-luna)**
- "What hoodies do you have?" → "See all 25 hoodies"; the page shows 25.
- "Show me navy hoodies in large under $70" → "See all 11 navy hoodies in L up to $70"; the page shows 11.
- Browser: "Do you have gray crewnecks under $60?" → answer "16 gray crewnecks" + button click → Products page with Crewnecks, Gray, and Up to $60 applied, showing 16.
- Grader-environment reproduction: "What quarter-zips do you have?" → "See all 11 quarter-zips".

---

## 4. Sold out in my size → in-stock alternatives (back end / agent)

**What changed**
- Before, the conversation ended at "XS is sold out".
- A new agent tool, `find_in_stock_alternatives(product, size)`, finds products **that have that size in stock**, closest first. The order is: ① the same design in another garment (e.g. Yale Mom Hoodie → Yale Mom Crewneck), ② a similar design, ③ the same category in the same color family, ④ the same category. Within a tier, the closest price comes first.
- Each suggestion comes with a reason ("same design, as a crewneck") and the quantity left in that size.
- Prompt rule: as soon as `check_stock` reports sold out, call this tool and suggest 2–3, named, with their reasons.

**Why it helps shoppers**
- Instead of "we don't have it", they hear "that size is sold out, but the crewneck with the same design has XS". No need to hunt again for the closest thing to what they wanted.

**Why it helps the business**
- **24% of size-level stock rows are sold out.** Each of those answers used to be a lost sale; now it can become a sale of an alternative.
- Steering demand toward products that still have stock also helps sell through inventory.

**Accuracy safeguards**
- Only products with `inventory.quantity` > 0 at the moment of the lookup are suggested.
- Prices, quantities, and product ids returned by the tool go into the ledger, so the Problem 6–7 validators check the numbers in the answer and the cards as before.

**What was verified (real gpt-6-luna)**
- On the Champion Reverse Weave Hoodie page, "Do you have this in XS?" → "Sold out in XS. Basic Hoodie Big Yale (15 left) and Crew Left Chest Hoodie (20 left) have XS." This matches the DB. The crewneck with the same design also has 0 in XS, so it was correctly left out.
- "I need the Fencing Left Chest Hoodie in large" → sold out in L + 2 similar-design hoodies (8 and 25 left in L).

---

## + Bulldog mascot (brand)

The bulldog from `99_Assets/YH_Bulldog` (taken from the Handsome Dan drawing in the course instructor's repository) was added as `frontend/src/components/YH_Bulldog.tsx` and placed around the site.

| Where | Role |
|---|---|
| Large bulldog on the right of the Home hero + "Handsome Dan approves." | The friendliness of the school mascot in the first impression |
| Small bulldogs on the 3 Home promise cards | A different coat color per card for visual rhythm |
| The 5 Home "Shop for" tiles | One bulldog per collection, inviting a click |
| Bulldog family in the Home family section (4 dogs of different sizes) | A visual joke tied to "Mom. Dad. Grandpa." |
| Products hero, empty results ("Handsome Dan sniffed around…") | Softens the disappointment of 0 results, with a "Clear all filters" button to recover right away |
| 404 page, About's visit section, chat avatar, footer | One consistent character across the site |

Campus photos were not used because of copyright. The source is credited in the footer.

---

## How to check it yourself

1. On Home, click the **Family** tile in "Who are we dressing today?" → **Hoodies** tab → size **XXL** → 5 pieces, each card marked "XXL in stock".
2. Ask the chat **"What hoodies do you have?"** → **"See all 25 hoodies →"** under the answer → the filtered Products page.
3. On the **Champion Reverse Weave Hoodie** product page, ask the chat **"Do you have this in XS?"** → sold-out notice + alternatives that have XS in stock.
4. Look at any product photo → every background is white.
