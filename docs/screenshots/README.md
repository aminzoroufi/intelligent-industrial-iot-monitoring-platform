# Screenshot evidence policy

Only screenshots captured from the running committed application with clearly
labeled synthetic data belong here. Do not add mockups, design-tool renders,
stale pages from an earlier build, or images whose source commit and scenario
cannot be identified.

The release screenshot is pending because the browser rerun after the live
loopback/cookie fix has not executed. The CI Playwright job must first pass the
desktop and mobile operator flow against a clean Compose build. Then capture the
fleet and device-detail views, record the source commit and named simulator
scenario in the image caption or adjacent Markdown, inspect for exposed tokens
or personal data, and add the real image to the README.
