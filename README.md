# Lably

**Blood Report Manager**

A single-purpose Windows desktop app for a pathology lab: fill in a form, generate a
blood report and its bill, print it on a real printer, and browse everything
printed before.

**No database.** All data lives in local JSON files under
`%APPDATA%\BloodReportApp\`, with an in-memory cache for instant history search.

## Run it

```
pip install -r requirements.txt
python -m app
```

Or just double-click **run.bat**.

## First use

Open the **Laboratory Profile** tab (the app starts there until it's filled in) and enter the
laboratory name, address, phone, registration number, **lab timings** and the
**holidays** (free text, optional - e.g. "Sundays & public holidays"), the **lab
technician's name**, and pick a logo and the technician's signature image.
One person signs the foot of the report: the **lab technician** who ran the tests, at
the bottom left. There is no pathologist field - the profile holds what gets printed
and nothing that does not. The bill is a separate document and carries its own *Printed By /
Billed By* line at its foot. The letterhead prints centred on the page, with the timings and holidays
on their own line under the contact details - change them in the profile and every
report printed from then on carries the new ones. A live preview shows the letterhead
exactly as it will print. Chosen images are copied into the app's own `assets` folder, so the report keeps
working even if you later move or delete the originals.

## Making a report

1. **New Report** tab: enter patient name, age, sex, referring doctor, sample details.
   The report number, the **Patient ID** and both timestamps are filled in automatically.
   The Patient ID (`PID-000001`, `PID-000002`, ...) is a read-only unique key: it is
   checked against every stored report before being handed out, so it can never
   collide - even after restoring a backup. Reopening a report keeps its ID, and
   **Duplicate as New** reuses the same ID so repeat visits by one patient stay linked.
2. Tick the panels you need — **CBC, Lipid, LFT, KFT, Blood Sugar, Thyroid**. Ticking a
   panel loads its tests, units and reference ranges; unticking removes them.
3. Type the results. Anything outside the reference range turns bold red and is marked
   **H** or **L**, both on screen and on the printout. Every row carries a **Sl No**
   beside the test name, renumbered as rows are added, deleted or a panel unticked, so
   a line queried off a printout can be found on the screen by its number. A
   sub-heading is a band across the grid rather than a line item, so it is not given
   a number.
4. Every cell is editable, and **+ Add Row** / **- Delete Row** let you report any test
   that isn't in the built-in panels.
5. **Billing Details** at the foot of the page prices the work. Every panel you
   ticked appears as one line - a lab bills for "CBC", not for each of its fifteen
   components - and the total, net payable and balance recalculate as you type.
   Each line carries a **Sl No**, the same numbering the printed bill uses.
   Enter the **Net Deposit** if the patient has paid something; the **Balance** is
   red while anything is owed and green once it is settled. Leave it all blank and
   nothing about the report changes. **Preview Bill / Bill PDF / Print Bill** on that
   card produce the patient's bill as a document of its own.
6. **Print Preview**, **Export PDF**, or **Save and Print** (which always saves first,
   so nothing is printed that isn't in the history). The preview has labelled
   **Zoom In / Zoom Out / Fit Page / Fit Width / 100%** buttons and a live zoom
   percentage, and answers `Ctrl` with `+`, `-` and `0`.

Reference ranges for Haemoglobin, RBC, PCV, ESR, HDL, Creatinine and Uric Acid are
sex-specific and re-resolve automatically if you change the patient's sex.

## Billing

One card, one output. The **Billing Details** card sits under the results grid on the
New Report page and feeds the bill:

* **The bill** - a document in its own right, with the lab's letterhead, a numbered
  services table, the paid amount spelled out in words and a *Printed By / Billed By*
  line at its foot. Printed at the counter, usually before any result exists.
  `Preview Bill`, `Bill PDF` and `Print Bill` sit in that card's header, `Ctrl+B`
  prints one from anywhere, and **Reprint Bill** in History prints a stored one.

**The report carries no charges.** A laboratory report is a clinical record: it gets
filed with a patient's history and photocopied for a consultant, and what the visit
cost has no business travelling with it. The two documents also print on different
paper - A4 portrait for the report, A5 landscape for the bill - so they could never
honestly have been one sheet.

The bill is laid out in [app/bill_html.py](app/bill_html.py), separately from
[app/report_html.py](app/report_html.py). Keeping them apart is what stops either
document quietly acquiring the other's furniture.

```
+--------------------------------------------------------------------------+
|                    MALLIGE DIAGNOSTIC CENTER                             |
|      #M-17, 1st STAGE, NRUPATUNGA ROAD, NEAR SHANTHI SAGAR COMPLEX       |
|         Opp. CORPORATION BANK KUVEMPUNAGAR, MYSURU-570023                |
|              Ph: 08212529999 Mob: 9964725222                             |
|--------------------------------------------------------------------------|
|                             Cash Bill                                    |
|--------------------------------------------------------------------------|
| Patient Name : Mr. PRASANNA C N    Bill No   : 416385                    |
| Patient No   : 147634              Bill Date : 30-Aug-2026 10.43.30 AM   |
| Age/Gender   : 67 Yrs / Male       Bill Type : Cash Bill                 |
| Phone No     : 9620055441          Doctor    : Dr. RAVIKUMAR KULKARNI    |
|--------------------------------------------------------------------------|
| +---+--------------------------------+-----------+--------------------+  |
| | # | Services                       |   Amount  |     Net Amount     |  |
| | 1 | USG-Abdomen & Pelvic Scan      |    950.00 |             950.00 |  |
| | 2 | URINE ROUTINE                  |     90.00 |              90.00 |  |
| |          Total Billed              |  1,040.00 |           1,040.00 |  |
| +---+--------------------------------+-----------+--------------------+  |
|                                     +-----------------+--------------+   |
|                                     | Net Payable Amt |     1,040.00 |   |
| Paid Amount : One Thousand Forty    | Net Deposit Amt |     1,040.00 |   |
|               Rupees Only           | Balance         |         0.00 |   |
|                                     +-----------------+--------------+   |
|                                                                          |
| Miss. NETHRA H M                    Miss. NETHRA H M                     |
| Printed By                          Billed By                            |
|                                                                          |
| Note:                                                                    |
| 1.  Please bring receipt while collecting the report                     |
| 2.  Beyond 01 month reports will not be preserved                        |
| 3.  All culture reports after 3-4 days                                   |
| 4.  Working Hours : Weekdays : 7.00 am to 9.00 pm ...                    |
+--------------------------------------------------------------------------+
```

**It prints on A5 landscape** - 210 x 148 mm, literally half an A4 sheet - while
the report stays A4 portrait. A bill is a counter slip, not a clinical record, and
half a sheet is the size the lab's own bill book uses. The two page setups are
named in [app/printing.py](app/printing.py) and every path (preview, printer,
exported PDF) is handed the same one, so all three agree.

Half a sheet is tight. The letterhead, identity block, closing figures, signatures
and standing terms are fixed cost; each service line is about eighteen points on
top. Three services fit comfortably; a longer bill flows onto a second slip rather
than truncating.

The closing figures are **one table cell, not three rows**. Qt breaks a page at
the nearest row boundary and will take one inside a nested table, so on a bill
long enough to need a second slip the box was being cut through - stranding
*Balance* at the top of slip two with nothing above it to say what it was the
balance of. Qt has no `page-break-inside: avoid`, so a single cell is the only
lever there is; the lines between the figures are drawn rules rather than table
borders, which is why it still looks like a box.

Getting it to fit turned up a Qt trap worth knowing: **Qt puts a minimum line box
around every block it lays out**, so a `<div>` used purely as a spacer costs about
five points whatever font size it is given. A dozen of those was eighty points -
a fifth of the page - spent on nothing. The rhythm is now cell padding on the
rows of a single page table, which has no such floor and is exact.

It is deliberately monochrome, Arial, and fully ruled. The report is a clinical
document and carries the lab's colours; a bill is an accounting document that gets
photocopied and filed, and every rule on it has to survive that. Qt paints an
unstyled table border in its own grey, so every border sets `border-color`
explicitly.

**Nothing on it may break in two.** The page is laid out at the *printer's*
resolution in the *printer's* font, neither of which is knowable when the HTML is
built, so a label that fits on screen can still wrap on paper - and `Net Payable`
over `Amt` is the difference between a bill and a mess. Every cell of fixed shape
(labels, amounts, the timestamp, the signatory names) is `white-space: nowrap` and
claims its natural width; only names and the standing notes are left breakable, so
an unusually long one gives way instead of shoving its column over its neighbour.
The two identity columns are separate tables inside a 50/50 shell, because in one
six-column table a long doctor's name on the right narrows the patient's name on
the left until it wraps.

The heading is the **bill type**, so a credit bill titles itself *Credit Bill*.
The **Printed By / Billed By** pair at the foot of the bill is one stored name printed
twice: the app has no user accounts, so the person who raised the bill is the person
standing at the printer, and a second field that could only ever hold the same value
would be furniture rather than data. The pair prints whether or not a name is on file -
*Billed By* is the line a patient comes back to when they query a charge, so with no
name the bill prints a rule to sign on rather than dropping the question.

One deviation, deliberate: the lab's slip prints the fourth column header as
**Net Am** where the word is cut short. This prints **Net Amount**. Everything
else matches the slip field for field.

| Field | Where it comes from |
|---|---|
| Bill No | Generated (`BILL-000001`, ...), overwrite it if the lab has its own numbering |
| Bill Date | Now by default; a date-**time** picker, not a text box |
| Services / Tests | One line per selected panel, taken from the results grid |
| Amount | Typed per service |
| Total Billed | Sum of the priced lines |
| Net Payable | The total billed - see below |
| Bill Type | Chosen; also titles the printed bill |
| Billed By | Typed, prefilled from the Laboratory Profile |
| Net Deposit | Typed; what the patient has already paid |
| Balance | Net Payable - Net Deposit |

Six decisions worth knowing about.

**The bill follows the panels.** Tick a panel and it arrives on the bill unpriced;
untick it and its line leaves with its amount. Every other amount stays where it
was, so re-thinking the panel selection halfway through never costs you the prices
you already entered. A test added by hand becomes billable under *Investigations*
as soon as you name it - the same heading it prints under.

**Blank is not zero.** A service with no amount is *unpriced*: it adds nothing to
the total and prints as a dash, not as a free test. That distinction is why amounts
are stored as typed text rather than as numbers.

**Nothing is totalled on disk.** `reports\<id>.json` holds only the service lines,
their amounts and the deposit. Every total is recomputed from those on open, so a
corrected amount always re-totals correctly instead of disagreeing with a stale sum
stored beside it. Money is `Decimal`, never `float`.

**A bill is timestamped, not just dated.** Two bills for one patient on one
morning have to be tellable apart at the counter, so the stored date carries the
second and the bill prints it: `30-Aug-2026 10.43.30 AM`. Bills written by the
first build stored the day alone and still open.

**The bill's own amount is spelled out**, on its own full-width line directly
under the services table, whether or not anything has been paid. A total can be
altered after the fact with one pen stroke and a sentence cannot, so the figure
the words exist to protect is the one being charged. The *paid* amount is spelled
out too, beside the closing figures - but only when something has actually been
paid, since on an unsettled bill it says nothing the Balance has not.

It gets the full width rather than sharing a row with the closing box. Everything
in that box is `nowrap` and claims its natural width whatever percentage its cell
is given, which left the sentence squeezed into the remainder and broken across
two lines on any bill over a few thousand rupees.

**The standing terms are offered, not imposed.** A brand-new profile opens with
the usual laboratory receipt terms already in the Bill Notes box, so a bill
printed on day one has a footer. Once the lab has a profile the box shows exactly
what was stored, blank included - prefilling every empty box would mean a lab
could never keep the notes cleared, because the defaults they deleted would come
back the next time they saved anything at all. **Use standard terms** puts them
back in one click.

**The paid amount is spelled out.** `One Thousand Forty Rupees Only`, in Indian
grouping - lakh and crore, not million. A figure can be altered after the fact with
one pen stroke; a sentence cannot. `billing.amount_in_words()`.

**Net Payable is the total billed.** Discounts, tax and insurance are out of scope,
so nothing is configured to adjust it. `billing.net_payable()` exists anyway, so
when an adjustment is specified there is exactly one place to apply it rather than
a dozen call sites summing their own totals.

Printing a bill saves the report first, for the same reason `Save and Print` does:
nothing leaves the counter unrecorded. Preview and PDF do not save. A bill with no
amounts on it is refused with a message rather than printed blank.

A report never carries a bill block, priced or not - see **Billing** above. The bill
number is allocated and stored on every report even when nothing was charged, because
it is the reference the lab quotes when a patient asks.

## Interface

A sidebar rail on the left (New Report / Report History / Test Templates /
Laboratory Profile, also `Ctrl+1..4`), and one page at a time on the right. Each page is a stack of
white cards on a light canvas.

The visual system lives in three files:

* [app/ui/theme.py](app/ui/theme.py) - the palette, the 8px spacing rhythm and
  the application-wide stylesheet. Every colour and size resolves against the
  tokens at the top, so a change there moves the whole app at once.

  Two Qt surfaces need naming explicitly or they come back black: the combo-box
  popup and the date pickers' `QCalendarWidget`. Both open in their own top-level
  window, which does not inherit the card behind it, so the global transparent
  `QWidget` background leaves Fusion to paint them - and Fusion paints them dark.
  Every part of the calendar is a separate widget (frame, navigation bar, day
  grid, year spin box) and each has to be styled by name.
* [app/ui/icons.py](app/ui/icons.py) - every icon and the app logo, drawn with
  QPainter on a 24x24 grid at a single stroke weight. Drawing them in code
  rather than shipping image files keeps the build one file, guarantees a
  consistent weight, and lets any icon be recoloured or resized on demand
  (the sidebar redraws its icons white when a page is selected).
* [app/ui/widgets.py](app/ui/widgets.py) - the shared building blocks: cards,
  page headers, stat tiles and empty states.

Two Qt-specific traps are worth knowing before editing the chrome, and both are
guarded by tests:

* **Cards holding a table or a text browser must be built with
  `elevated=False`.** A `QGraphicsDropShadowEffect` renders a widget's children
  through an offscreen pixmap, and scroll-area children then paint outside the
  card's bounds.
* **The New Report page scrolls.** Laying its cards out directly means that on a
  short window the page needs more height than it has, and Qt resolves that by
  squeezing the stretchy card below its minimum - which paints the results grid
  over its own buttons.

## Test Templates

The six built-in panels are only a starting point. The **Test Templates** page
lets you build the panels your lab actually runs, once:

* **Create your own panels** (Urine Routine, Semen Analysis, whatever you run).
* **Add sub-headings** inside a panel - a section title such as
  `DIFFERENTIAL COUNT` or `PHYSICAL EXAMINATION`. A heading has no result, unit
  or range; it prints as a bold band across the results table.
* **Edit the built-ins too** - rename a test, fix a unit, change a reference
  range, add or remove rows. Edited panels are marked *(edited)* in the list,
  and **Reset** restores the one you are looking at to what it shipped with.
* Separate **male and female reference ranges** per test; the form picks the
  right one from the patient's sex and re-picks it if the sex is changed.

Everything you save here shows up on the New Report page immediately - no
restart - and is used by every report from then on.

Only your *differences* are stored, in `panels.json`, never a full copy of the
defaults. A panel you have not touched keeps tracking the shipped version, so a
later release can correct a reference range without overwriting your work, and
"Reset" is simply dropping your override.

## Editing a saved report

A report that has been saved and printed is a medical record. Opening one from
History shows it **read-only**, with a banner naming the report. You can still
preview, export and reprint it - none of that changes the record - but the
fields are locked.

**Unlock to Edit** asks for the edit password. Deleting reports asks for the
same password, since deleting is just as irreversible as editing.

### How the password is validated

Set the first time you try to edit or delete something. It is never stored:
the app generates 16 random bytes of salt and runs the password through
**PBKDF2-HMAC-SHA256, 260,000 iterations**; only the salt, the iteration count
and the resulting hash go into `security.json`. Checking a password repeats that
computation with the stored salt and compares the hashes with
`hmac.compare_digest`, which takes the same time whether the first byte differs
or the last - a plain `==` leaks how much of a guess was right.

The iteration count is stored per record, so the cost can be raised in a future
version without locking anyone out.

**What this does and does not protect.** It stops someone at the counter quietly
altering or deleting a finished report. It is *not* protection against someone
with real access to the machine: reports are plain JSON in `%APPDATA%` and
anyone who can read that folder can edit them in Notepad. Encrypting them would
mean a forgotten password destroys every report, which for a small lab is far
worse than the risk it removes - use a Windows account password if you need
that level. If the password is forgotten, delete `security.json` from the data
folder to clear it.

## Field rules

Validation works in two layers, in [app/validators.py](app/validators.py):

* **While typing** - a character filter stops the wrong characters ever reaching
  a field. No digits in the patient name or the referring doctor, digits only in
  the age box (capped at three), no letters in the lab phone number.
* **On save** - the rules a character filter cannot express: the name needs at
  least two letters, the age is required and must be plausible *for its unit*
  (max 130 years / 36 months / 400 days), and the lab email and phone must look
  real. The age box tints red the moment the value stops making sense, and
  saving is blocked with one specific message at a time rather than a list.

### Every field, and what it accepts

| Field | Rule |
|---|---|
| Patient name, Referring doctor | Letters and name punctuation only. No digits. |
| Age | Digits only, max 3, plausible for its unit |
| Age unit, Sex | Fixed choices |
| Patient ID, Report No | Generated, read-only |
| Sample type | Letters only |
| Collected / Reported on | **Date-time pickers**, not text |
| Remarks | Capped at 300 characters |
| Test name (grid and templates) | Words, numbers and lab punctuation - `SGOT / AST`, `Vitamin B-12`, `T3 (Total)` |
| Result | Number **or** qualitative word, max 40 chars |
| Unit | A unit, not prose: `g/dL`, `%`, `/cmm`, `mm/1st hr`, `10^3/uL`. A bare number is refused |
| Reference range | A range (`13.0 - 17.0`), a bound (`< 200`), or a single qualitative word (`Absent`) |
| Bill Type | Fixed choices: Cash / Credit / Insurance Bill |
| Billed By | Letters and name punctuation, max 40. Optional |
| Bill Notes (profile) | Up to 6 lines, 150 characters each. Blank means no footer |
| Bill No | Letters, digits, spaces and `/ -`, max 24. Blank is filled in on save |
| Bill Date | A **day picker**, not text |
| Amount, Net Deposit | Digits and at most two decimals. Blank means "not priced" |
| Lab name, address, degrees, footer | Printable text, length-capped |
| Phone, Mobile, Phone No | Indian only: exactly 10 digits, stored as `+91 9845012345` |
| Email | Must look like an address |
| Registration no. | Alphanumeric with `/ - .` |

Two of these are worth explaining.

**Phone numbers are Indian, and exactly ten digits.** All three - the patient's,
the lab's phone and its mobile - take ten national digits and nothing else. They
may be typed in any shape (`9845012345`, `98450 12345`, `+91 9845012345`,
`0091-98450-12345`) and are stored and printed in one: `+91 9845012345`. A
landline fits the same rule once its trunk 0 is dropped, so `0821 2529999` is
stored as `+91 8212529999`.

A country code is only stripped when the length says it is one. `9198765432` is a
perfectly good ten-digit mobile that happens to begin with 91, and reading that as
a prefix would silently turn it into an eight-digit number.

**Dates are pickers, not text boxes.** They used to be plain fields, which meant
`asdf` could print as the collection date on a medical report. Making the invalid
state unreachable is more reliable than validating it afterwards.

**Reference ranges reject the middle ground.** A range must be a real range, a
real bound, or a plain word. What is refused is text that *looks* numeric but
cannot be parsed - `13 abc`, `12 -`, `about 200`. Those are the dangerous ones:
they sit in the reference column looking authoritative while the H / L flagging
silently never fires. A test asserts that every range the validator accepts as
numeric is one the flagger can actually use, and another asserts that all six
built-in panels satisfy the rules the app enforces.

Invalid cells in the results grid and the template editor show in **bold red
italic** with the reason in a tooltip, and saving stops on the first one,
naming the row and the field.

**Results are deliberately not restricted to numbers.** Pathology results are
routinely qualitative - "Nil", "Absent", "Trace", "Positive", "<0.01" - and a
numbers-only rule there would make the app unable to report a negative serology
or a normal urine deposit. Only absurd input (over 40 characters) is rejected.
Numeric results are still compared against the reference range for H/L flagging.

**A deposit larger than the bill is refused.** Refunds are out of scope, so a
negative balance can only be a slipped keystroke, and saving stops with the two
figures named. An amount that is not a number is marked in bold red italic in the
billing grid, left out of the running total, and blocks saving - the same treatment
a bad unit gets in the results grid.

Typing rules apply to typing and pasting, not to loading a stored report: an
older record whose name contains a digit opens unchanged rather than being
silently rewritten.

## Notifications

Saving, clearing, printing, exporting and deleting all raise a coloured banner in
the top-right of the window - green for success, blue for information, amber for
"you need to fix something first". It fades on its own, so the most frequent
action in the app never costs an extra click to dismiss a dialog. Only genuinely
destructive actions (Clear with unsaved typing, and deleting reports) stop and
ask for confirmation.

## History

The **Report History** tab lists every saved report. Search by patient name, patient ID, report number or
referring doctor. For any row you can **Open** it for editing, **Duplicate as New**
(keeps the patient details, clears the results — the repeat-visit case), **Print
Preview**, **Reprint** (the report), **Reprint Bill** (the bill, on its own A5 page),
**Export PDF**, or **Delete**. A report that was never charged for says so rather
than printing a blank bill.

## Where the data lives

```
%APPDATA%\BloodReportApp\
  lab_profile.json        letterhead, bill notes, default billing clerk
  counter.json            report, patient and bill serial numbers
  panels.json             your test templates (only your edits, not the defaults)
  security.json           the edit password, salted and hashed - never the password
  index.json              history list (cache; rebuildable)
  reports\<id>.json       one file per report - the source of truth
  assets\                 logo and technician signature images
```

Reports are written atomically (`.tmp` then replace), so a crash mid-save can't corrupt
one. If the history list ever looks wrong, **File → Rebuild History Index** re-scans the
`reports` folder and rebuilds `index.json` from the actual report files.

To back up or move to another machine, copy the whole `BloodReportApp` folder.

### Backup to Google Drive

In **Laboratory Profile → Backup Folder**, press **Use Google Drive** (or **Browse...**
and pick any folder). **Open** shows the folder in Explorer, as does
**File → Open Backup Folder (Google Drive)**. If Drive is not installed, **Use Google
Drive** offers to open its download page. From then on every report you save is also
copied there:

```
<backup folder>\
  2026\
    09-September\
      BR-000012-Ravi-Kumar.pdf          the printed report, openable on any phone
      data\BR-000012-Ravi-Kumar.json    the data file (restorable)
```

One folder per year and one per month inside it, by the month the report was made, so
finding "that report from last March" is two clicks in Drive.

This relies on **Google Drive for desktop** (google.com/drive/download) being installed and
signed in: it mirrors that folder to the Google account, so the app never needs to talk to
Google itself and there is no login inside the app to expire. OneDrive or any other sync
folder works the same way. Saving never fails because of the backup - if the folder is
missing or unwritable, the report is still saved locally and a warning is shown. Saving a
report again after correcting the patient's name replaces the earlier copy rather than
leaving two spellings in Drive. Deleting a report in the app does not delete its backup.

## Keeping it aligned

Three rules hold the two documents straight, all of them learned the hard way.

**Nothing uses `cellpadding` for vertical space.** It applies to all four sides,
so a block that wanted a little air above it also indented itself - and with
three different amounts in use, the bill had four different left edges running
down it. Space between blocks belongs to the band that holds them.

**Qt honours `white-space: nowrap` only on blocks and table cells, never on an
inline `<span>`.** So a long line cannot be told "break between these pairs, not
inside a value" - it breaks wherever the last character fits, which printed
`Reg. No KA/SMG/` on one line and `2019/118` on the next. Where a line might not
fit, the letterhead chooses its own breaks instead of leaving it to the layout.

**A field's value column is set to `width="100%"`.** That is what keeps a colon
against its label: told to fill the row, the value takes all the slack and the
label and colon keep their natural size. Without it Qt shares the surplus out,
and a column of short values pushes every colon clear of the word it belongs to.

There is a test for each of these, and two of them measure the rendered pixels
rather than the markup - `PrintedAlignmentTests` renders a page, finds the left
edge of every line on it and fails if they disagree by more than a few points.
Alignment is a property of the printed page, and that is where it is checked.

## Printing

Printing goes through the standard Windows print dialog, so any installed printer works.
The report prints A4 portrait; the bill prints A5 landscape, half an A4 sheet.
Each document's page setup is used for preview, printer and PDF alike, so all
three produce identical pages. Choosing "Microsoft Print to PDF" in the dialog is a good way
to test without using paper.

**Print Preview** is the app's own dialog, not Qt's. Qt's `QPrintPreviewDialog`
draws its zoom controls as icon-only tool buttons from a resource bundle compiled
into the print-support plugin, and a packaged build routinely loses it - the buttons
are still there but draw nothing, so the preview looks as though it cannot be zoomed
at all. `printing.PreviewDialog` builds the same `QPrintPreviewWidget` with buttons
that carry their own text: **Zoom Out / Zoom In** either side of a live percentage,
then **Fit Page**, **Fit Width**, **100%** and **Print...**. `Ctrl` with `+`, `-`
and `0` do the same. Zoom is clamped to 25%-800%, and a control that cannot do
anything more is disabled rather than clicking dead.

One Windows quirk worth knowing: a print driver can **refuse a whole `QPageLayout`**
and report it only through a return value. The refusal is silent and total - the
printer keeps whatever page it had, usually Letter portrait - which is how an A5
landscape bill ended up printed down the middle of a Letter sheet on machines whose
default printer does not advertise A5. `printing._configure` reads that return value
and falls back to setting page size, orientation and margins one at a time, which
such drivers accept.

## Layout

```
app/
  __main__.py       entry point
  storage.py        JSON local storage + cache, atomic writes, index rebuild
  models.py         LabProfile, Report, TestRow, Billing, BillItem
  billing.py        bill arithmetic: amounts, totals, balance, billable services
  panels.py         panel catalogue + H/L range checking
  report_html.py    Report -> printable HTML letterhead and tables
  bill_html.py      Report -> the standalone printable bill
  printing.py       print / preview / PDF via QPrinter
  ui/               main_window, report_form, history_view, settings_view
  ui/theme.py       palette and application-wide stylesheet
  ui/toast.py       the notification banner
  ui/templates_view.py   the Test Templates page
  ui/password_dialog.py  set / ask for the edit password
  validators.py     field rules (typing filters + save-time checks)
  templates.py      editable test panels: overrides, custom panels, sub-headings
  security.py       the edit password (PBKDF2-SHA256)
  util.py           filename sanitising
```

## Tests

```
python -m unittest discover -s tests -t . -v
```

Or double-click **run_tests.bat**. 566 tests, no third-party test runner needed -
just the standard library plus PySide6's offscreen platform for the widget tests.
Every test runs against a temporary APPDATA folder, so the suite never touches
your real report data.

```
tests/base.py              sandbox harness shared by all tests
tests/test_models.py       dataclass serialisation (the on-disk format)
tests/test_panels.py       panel catalogue + H/L reference-range checking
tests/test_billing.py      bill arithmetic: parsing, totals, balance, sync
tests/test_validators.py   field rules: what may be typed, what is caught on save
tests/test_templates.py    editable panels, sub-headings, reset to default
tests/test_security.py     password hashing, verification, corrupt records
tests/test_storage.py      serials, atomic writes, index integrity, recovery
tests/test_report_html.py  printable report, HTML escaping
tests/test_bill_html.py    the standalone bill: layout, figures, escaping
tests/test_ui.py           form, billing, bill printing, history, sync
```

## Sending the app to someone else

This is a **Windows desktop app, so it builds to a .exe, not an .apk** - APK is
the Android package format, and this app does not run on Android.

```
build_app.bat
```

or

```
pip install pyinstaller
python -m PyInstaller --noconfirm --distpath "%USERPROFILE%\Desktop" Lably.spec
```

The result is a single **`Lably.exe` (~46 MB) on your Desktop**. The exe is stamped
with `version_info.py`, so Explorer's **Properties → Details**, Task Manager and the
SmartScreen prompt all name **ACHUTHTECH** as the publisher, and a
**"Developed by ACHUTHTECH"** card shows for a moment on every launch. That one file is
the whole app - send it on WhatsApp, email or a pen drive with no zipping. The
recipient double-clicks it; Python and PySide6 are not needed on their machine.

Two things worth telling them:

* Windows SmartScreen will say "Windows protected your PC" the first time,
  because the build is not code-signed. **More info -> Run anyway.** A
  code-signing certificate is the only way to remove that prompt.
* Their reports are stored in their own `%APPDATA%\BloodReportApp\`, never
  inside the .exe. So you can send an updated Lably.exe later and it picks up
  every report they already have.

### Why one file, and what it costs

A one-file build unpacks itself into a temp folder on each launch, so it takes
a few seconds to appear - the price of being a single shareable file. If you are
setting up a machine yourself and want instant startup, build the folder version
instead by replacing `EXE(...)` in `Lably.spec` with the standard
`EXE(..., exclude_binaries=True)` + `COLLECT(...)` pair, or just run the app from
source with `run.bat`.

`Lably.spec` excludes the Qt modules the app never uses (WebEngine, Quick, 3D,
multimedia, SQL) - without that the build is roughly three times the size.

### Renaming the app

Everything user-facing comes from [app/branding.py](app/branding.py) - change
`APP_NAME` there and rebuild. Leave `DATA_FOLDER` alone: renaming it would
orphan every report already stored on disk.
