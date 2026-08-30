# Validation record

Validated on 30 August 2026.

## Executed checks

- 23 automated tests passed.
- All Python source files compiled successfully.
- The Doodle page title, hero logo, single search field and hidden landing-page navigation are covered by a branding regression test.
- The A4 sample PDF was verified as a 210 x 297 mm page.
- The custom-page exporter was tested against requested PDF MediaBox dimensions.
- The default 58 mm layout was verified as a 3 x 4 grid containing 12 circles.
- The cut-guide path geometry was checked programmatically at 58 mm.
- The 12-position circle sheet was rendered and checked to ensure every position contains artwork.
- The A4 colouring page, 58 mm circle sheet and Doodle calibration page were rendered to PNG and inspected visually.
- The minimalist homepage styling was rendered in Chromium at 1440 x 900 and inspected visually.
- The OpenAI adapter is covered with a simulated SDK response, including base64 decoding and request parameters.
- The three application layout branches were executed through a non-interactive Streamlit smoke-test harness.
- Both the new `DOODLE_DATA_DIR` setting and legacy data-directory compatibility are tested.

## Environment limitation

Streamlit is not installed in the build container, so the live Streamlit server was not launched here. The interface source was compiled and exercised through the smoke-test harness; the homepage CSS and wordmark were separately rendered in Chromium. A live OpenAI request was not made without an API key.

## Printing caveat

PDF geometry can be exact while a printer driver silently rescales output. Print at Actual size / 100%, disable fitting options, and use the supplied calibration page before producing a batch.
