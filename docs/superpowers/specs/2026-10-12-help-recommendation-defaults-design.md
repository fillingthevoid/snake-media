# Help and recommendation defaults

Approved scope: shorter Help and remembered recommendation preferences on Discord and Telegram.

Help has Request media, Recommendations, My requests, Server status and More. More shows season/expiry guidance and direct Extend/Keep navigation with Back to Help. Existing slash commands remain available. Menus retain five-minute inactivity expiry; expiry notices remain six hours.

Recommendations persist the last explicitly chosen valid media type and genre per immutable source/user ID. Reopening shows that pair and Find suggestions, Change preferences and Cancel. Generation never runs merely on opening. New users keep the existing type and genre picker. Change preferences returns to type selection. Selection stays owner/destination scoped, has the existing generation limit, and uses ordinary poster confirmation before any media mutation.

Use dedicated recommendation-settings rows in the existing pending/settings table, with stable requestKey recommend-settings:source:userId. Read only matching source/user/state/key; validate serialized preference values. Store only after a successful conditional recommendation claim and generation selection. Writes use native Data Table nodes, never SQLite. Storage errors fall back to normal selection or generation without saving, preserving Watch preferences and unrelated settings. No global lock is added for presentation preferences.

Tests cover no automatic generation, invalid and foreign settings, owner scopes, saved and changed filters, native read/upsert filters and graph placement, both Help adapters and existing media bindings. Export active workflows privately, patch only owned code/edges, publish and use guarded n8n restart; rebuild only Discord after reviewed source changes. Smoke-test Help and recommendation selection without final media confirmation. Preserve rollback exports and prior bot image.
