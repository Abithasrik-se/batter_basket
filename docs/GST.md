# GST notes

**Not tax advice. Confirm every point with your CA.**

## What the system does
Settings → GST controls billing:
| GST scheme | Document printed | GST on bill |
|---|---|---|
| Regular | **Tax Invoice** | Charged. CGST + SGST split (Tamil Nadu intra-state) |
| Composition | **Bill of Supply** | None charged to customer |
| Unregistered | **Bill of Supply** | None |

- Each product has `HSN code` (default 2106) and `GST %` (default 5.00). Each order line **copies the rate it was billed at**, so a later rate change never alters old bills.
- "Selling prices already include GST" (default on) back-calculates tax from the price. Switch it off to add GST on top.
- Invoice numbers: `PREFIX/FY/00001`, financial year April to March, gap-free.
- Business GSTIN, customer GSTIN (hotels) and business address are snapshotted on each invoice.

## Open questions for your CA
1. Which scheme are you registered under (regular or composition)?
2. What GST rate and HSN applies to your packaged batter? Public sources disagree: the official rate schedule lists idli/dosa batter at 5%, some reports and documents say 18%; powdered mixes are treated differently from batter.
3. Is GST charged on the delivery fee? (The system currently does not tax it.)
4. Should composition-scheme invoices carry any special wording?
