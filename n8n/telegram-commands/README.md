# Telegram commands

/request <title> enters the existing request workflow. /help and /start return
instructions. Account authorization runs before replies. Plain messages, status,
retention commands and button callbacks retain their existing routes.

build.py patches a compatible private Telegram export and requires the bot's public
username to ignore commands addressed to other bots. Preserve native credentials;
keep private exports outside Git. The sanitized current snapshot already includes
the parser: configure its bot username before publishing.

Telegram command menu can be registered in BotFather with /setcommands:

```text
request - Request a movie or series
help - Request and expiry instructions
status - Your downloads and expiry
```

The menu lists commands; workflow nodes implement their behavior.
