# Asian Hardware and Paints — Product Requirements & Build Handoff

## Original problem statement
The user supplied **“ASIAN HARDWARE AND PAINTS — Complete Web Application Master Prompt”** for a real hardware and paints retailer in Ambad, Nashik, Maharashtra, established in 2019. It calls for a premium public one-page site plus a protected owner dashboard with fast POS billing, GST invoices and thermal printing, contractor quotations, 500+ searchable inventory products imported from the owner's PDF, stock management, customers/khata, reports, and store settings. The owner provided two store contact numbers (+91 84118 80222 and +91 82089 68883), GSTIN 27CHXPC0935Q2ZK, required footer credits to Dragosaurabh and Ready2UP, and a complete 14-page inventory PDF: `inventory - Asian Hardware and Paints.pdf` at https://customer-assets-0z36b82j.emergentagent.net/job_966b5f60-8d40-4a8d-8f0f-0992bd913e19/artifacts/o4plds16_inventory%20-%20Asian%20Hardware%20and%20Paints.pdf.

The original brief requested Next.js 15 + TypeScript + SQLite + NextAuth. The user explicitly approved using the available **React + FastAPI + MongoDB** stack to prioritize a working experience. The user also explicitly authorized generating the site imagery with AI instead of uploading real store photographs.

## Personas
- **Owner/counter staff:** Search rapidly, invoice 10 items, print or share, hold a cart, serve the next customer.
- **Contractor/builder:** Request an itemized quotation, receive it by WhatsApp, purchase on credit.
- **Homeowner/visitor:** Discover product categories, locate either store, call, WhatsApp, or send an enquiry.

## Static core requirements
- Public site: two branches, business facts, categories, brands, direct contact, enquiry form, mandatory footer links, responsive layout.
- Admin: private owner login; dashboard overview; POS product fuzzy search, keyboard controls, item edits, discounts, configurable GST and payment modes, invoice PDFs/thermal format, hold/resume and offline draft protection.
- Quotations: catalog/custom lines, validity/terms, PDF, WhatsApp share, status progression, accepted quotation to bill.
- Inventory: import the complete PDF catalogue, CRUD, CSV import/export, physical stock reconciliation audit.
- Customers: contact details, credit/khata balance, purchase history and payment ledger.
- Reports/settings: sales, stock, product/category, GST, customers and quotation conversion, store and print preferences, password change.

## Architecture decisions
- React SPA uses React Router, shadcn/ui primitives, Lucide icons, Fuse.js fuzzy matching, Recharts and responsive CSS. Browser API calls use only `REACT_APP_BACKEND_URL`.
- FastAPI endpoints use a single configured MongoDB database via only `MONGO_URL`, Pydantic inputs, server-side financial calculations with Decimal rounding, and reportlab invoice/quotation PDFs.
- Single shared organization: owner authentication only; bcrypt password hashing; JWT held in an httpOnly SameSite cookie. All admin data APIs require server-side verification. Browser/API are same-origin; optional credentialed CORS is enabled only for explicitly configured origins, never wildcard.
- PDF inventory was visually checked, extracted to `backend/data/products.json`, and bootstrapped once with **506 source rows**. Initial stock **0**, purchase prices **0**, GST **18%** and blank HSN until the owner verifies each product. Duplicate source names are retained as separate SKU rows.
- Products cache in IndexedDB, bill draft autosaves to localStorage every five seconds, and disconnected bills queue locally. Offline receipts are **provisional only**; the final sequential tax invoice is assigned on successful sync.
- Generated storefront/interior/product photos are locally hosted and explicitly described on the website as illustrative rather than authentic store photography.
- Main routes: `/`, `/login`, `/admin`, `/admin/billing`, `/admin/quotations`, `/admin/quotations/:id`, `/admin/inventory`, `/admin/inventory/:id`, `/admin/customers`, `/admin/customers/:id`, `/admin/reports`, `/admin/settings`.

## Implemented — 2026-09-24
- Public editorial site with responsive mobile navigation, AI-generated imagery, 10 category links, brands, both stores, live enquiry submission, click-to-call/WhatsApp and exact required footer links.
- Owner login/logout, private APIs, dashboard sales/activity/charts and action shortcuts.
- POS with 506-product instant fuzzy search, keyboard shortcuts, quantity/rate/discount controls, per-product GST, cash/UPI/card/credit/mixed payments, credit customer linkage, hold/resume, WhatsApp, PDF and thermal/A4/A5 documents. Invoice numbering `AH/YYYY-YY/NNNNN` is sequential; quotation numbering uses `QT/...`.
- Quotation list/builder with custom lines, valid-until date, PDF and WhatsApp; accepted quotes convert once to bills.
- Inventory forms, stock adjustment audit, CSV template/import/export, product image upload to MongoDB; customer creation, ledger, payments and WhatsApp reminder; date-range sales, product/category, GST, stock, customer and quote conversion reports; store/print/password settings.
- Customer detail loading guard prevents provisional balance/actions before the account data arrives. Synthetic verification records were cleaned; catalog restored to 506 rows with zero initial stock and next invoice/quote counters reset to 1.
- Verification: frontend production build succeeds; testing agent executed 12/12 backend regression checks and browser journeys; thermal/A4 invoice and quotation PDFs were rendered and visually inspected; customer loading fix self-checked with browser screenshots.

## Implemented — 2026-09-24 (V2 redesign & optional GST)
- **Light design system** (`frontend/src/styles.css`, `index.css`): #F8FAFC canvas, white rounded-2xl cards with soft shadow, slate typography (Plus Jakarta Sans display + DM Sans body), royal-blue primary with amber accents, pastel pill badges, 150 ms micro-interactions. Applied to public site, login and every admin page.
- **Optional GST, off by default.** `includeGst` flag on bills and quotations (backend `SaleInput`/`QuoteInput`, `calculated_lines(..., include_gst)`; frontend `calculateCart(..., includeGst)`). Off → document is **ESTIMATE / CASH MEMO** with no tax lines; on → **TAX INVOICE** with GSTIN, taxable value, CGST/SGST (IGST outside Maharashtra). Prices are GST-exclusive. Single `AH/` series. Quote → bill conversion carries the flag; held bills preserve it.
- **PDFs** (`backend/pdf_export.py`): 80 mm thermal (Item | Qty | Rate | Amount, total items/pcs, payment/change lines) and A4/A5 (framed, Marathi name rendered via PIL+RAQM, both phone numbers, alternating rows, terms box, authorized signatory) both omit GST rows/GSTIN when the flag is off.
- **POS rebuild**: category pills with counts, product rows with stock badge + price + `[+] Add`, 44 px qty steppers, editable rate/discount, segmented payment pills (Cash / UPI-GPay / Card / Khata-Credit / Mixed), cash change, Print (F8) / Save & new / WhatsApp / Hold / A4 PDF, quick-add-customer modal. Formatted WhatsApp text via `lib/share.js`.
- **Mobile counter mode** (<800 px): Products / Current Bill tabs and a floating bottom cart bar (portaled to body).
- **Quotation builder**: validity dropdown (7/15/30/45/60/90 days), `+ Add custom item` with qty, GST toggle, formatted WhatsApp share, status actions, convert to bill.
- **Homepage refresh**: framed hero photo with glass badge, amber kicker, Call Now / WhatsApp Us CTAs, white stat cards, light footer with mandatory credits.
- Verification: testing agent iteration 2 — backend 24/24 pytest (new `tests/test_gst_toggle_flow.py`), all frontend flows pass; floating-bar containing-block bug fixed and re-verified. Database purged again: 506 products, zero stock, counters reset to 1.

## Prioritized backlog / next tasks
### P0 — needed before the owner issues real compliant invoices
1. Owner/accountant confirms correct **GST rate and HSN** for each product, verifies pricing basis (exclusive/inclusive of GST) and checks the printed invoice against accounting advice. Current imported values do **not** establish legal tax accuracy by themselves.
2. Owner performs physical counts and enters purchase costs; imported negative PDF quantities represent historical movement, not available stock. Initial inventory valuation/profit is not meaningful until costs and stock are entered.
3. Change the seeded owner password in Settings before using the app with real financial/customer data.
4. If uninterrupted **legally numbered tax invoices while completely offline** are required, design a controlled number reservation or local-first authoritative database. Current offline output is correctly marked provisional and syncs to a numbered invoice after reconnecting.

### P1 — next product improvements
- Per-branch stock quantities and inter-store transfers; current stock has a location label but one quantity per product.
- Column sorting, multi-category filtering, bulk price update and fuller import validation/preview.
- Supplier purchasing and returns/credit notes; stronger cancellation and invoice correction workflows.
- Product transaction history to include quotations as well as bills and adjustments.
- Verify Store 2 opening hours, replace illustrative photos with actual storefront images, collect authentic review quotes.
- Date-based report PDF export and an invoice archive/search view.

### P2 — later enhancements
- Barcode scanner UI refinements, automated reordering suggestions, fuller analytics and contractor-specific wholesale price lists.

## Next action for owner
Sign in at `/login` with the initial credentials specified in the brief, change the password, then validate HSN/GST, physical stock counts, and purchase prices before using tax invoices for real sales.