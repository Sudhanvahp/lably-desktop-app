# What's new in this build

Two changes. Nothing you have already saved is affected: existing reports, bills
and the laboratory profile all open and print exactly as before.

---

## 1. You can now set how every line on the report looks

**Laboratory Profile → Text Appearance.**

Pick a region of the report from the list, and set:

| Control | What it offers |
|---|---|
| **Alignment** | Left, Centre, Right |
| **Style** | **B**old, *I*talic, <u>U</u>nderline |
| **Font** | 13 faces that ship with Windows (Segoe UI, Calibri, Arial, Times New Roman, Georgia, Cambria, Garamond, Courier New and more) |
| **Size** | 5pt to 48pt, in half points where the body of the report lives |
| **Colour** | Any colour, from the standard Windows colour picker |

The preview underneath is a whole sample report and redraws as you go, so you
can see the change before you save it. It is drawn by the same code that drives
the printer, so what you see is what comes out.

### The 17 regions

Top to bottom, the way you read the sheet:

Laboratory name · Sub-heading · Document title · Report number · Patient labels ·
Patient details · Panel titles · Sub-headings inside a panel · Column headings ·
Results · H/L legend · Remarks · Amounts and totals · Signatory names ·
Signatory roles · End of Report · Footer

### Putting things back

- **Reset this text** — puts one region back to the standard layout.
- **Reset everything** — puts the whole report back.

Regions you have changed are marked with a `*` in the list, and the line under
the controls names them, so you can always see what you have changed without
opening all seventeen.

### Two things it deliberately does not do

**It does not touch the bill.** A bill is an accounting document - it gets
photocopied, faxed and filed - and its layout is the ruled form your lab already
issues. One set of controls answering for two documents would mean never being
quite sure which one a change was about to land on. The bill prints the way it
always has.

**It only stores what you actually changed.** Put a control back where it
started and nothing is stored for it at all. So a profile you have never
restyled prints exactly what it printed before this feature existed, and
centring your letterhead does not quietly freeze the size of every other line on
the page.

---

## 2. The bill date now reads `06 Sep 2026`

Day, month spelled out, year - on the bill and in the bill summary on the
report. The month is spelled out because `06-09` and `09-06` are the same six
characters and are read opposite ways in different countries.

**The time is no longer printed.** It used to read `30-Aug-2026 10.43.30 AM`.
The exact second is still stored with every bill, so nothing is lost and it can
be put back - but it no longer appears on the printed slip. If you rely on the
time to tell apart two bills raised for the same patient on the same morning,
say so and it can come back.

---

## Notes

- The version in the footer still reads **v1.3**; it has not been bumped for
  this build.
- Full documentation for everything else is in `README.md`, alongside this file.
