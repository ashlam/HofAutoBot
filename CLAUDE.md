# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HofAutoBot2 is a Python-based web game automation bot using Selenium to drive a Chrome browser. It automates gameplay on a web RPG (pim0110.com), handling boss battles, PVP arenas, stage grinding, and character management. The GUI is built with PyQt5.

All UI text, logs, and code comments are in Chinese. Use Chinese for all user-facing output.

## Development Environment

- Python 3.9+
- Virtual environment at `.venv/`
- Dependencies in `requirements.txt` (selenium, PyQt5, webdriver-manager, opencv-python-headless, pytesseract, Pillow, numpy, requests)
- No build step; run Python files directly
- Chrome browser must be installed (webdriver-manager handles ChromeDriver)

### Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the GUI application
python start_up_window.py

# Run the CLI version (deprecated, mainly for testing)
python scripts/hof_auto_bot_main.py

# Run a single test file
python test_action.py
python tests/test_boss_battle_manager_vip.py

# Run with pytest
python -m pytest tests/
```

## Architecture

### State Machine Pattern

The bot core (`scripts/hof_auto_bot_main.py::HofAutoBot`) uses a state machine pattern. `run_once()` delegates to the current state's `process()` method, which decides the next state.

Key states in `scripts/states/`:
- `prepare_boss_state.py` - Entry point; decides between boss/PVP/stage based on cooldowns/stamina
- `normal_boss_state.py` - Handles regular boss battle loop with random delays
- `vip_boss_state.py` - Handles VIP/rare boss battles with log-based cooldown tracking
- `wait_vip_boss_state.py` - Idle waiting for VIP boss spawn time
- `pvp_state.py` / `world_pvp_state.py` - Arena battles
- `normal_stage_state.py` / `time_limited_stage_state.py` - Stage grinding
- `idle_state.py` - Sleep/wait state with callback to next state
- `reconnect_state.py` - Auto-login on disconnect
- `update_character_state.py` - Scrapes character data from game pages

States transition by calling `self.set_state(next_state)` which updates `bot.current_state`. State instances are created via `StateFactory` to avoid circular imports.

### Action Execution System

`scripts/advanced_action_executor.py` + `scripts/advanced_element_finder.py` implement a paired factory pattern:

- `AdvancedActionExecutorFactory` maps `trigger_type` strings to executor objects that perform Selenium actions (click, select, etc.)
- `AdvancedElementFinderFactory` maps the same `trigger_type` to finder objects that locate DOM elements via XPath or element name

Action configs (`configs/server_*/action_config_advanced.json`) define action groups as arrays of `{trigger_type, value}` steps. The `AdvancedActionManager.execute_advanced_action()` runs a group sequentially.

Performance optimization: `AdvancedActionManager.batch_selected_characters_actions()` detects the pattern "clear team + select N characters + start battle" and executes it in a single JavaScript injection instead of individual Selenium calls.

### Configuration System

Configs are JSON files in `configs/`:

- `server_address.json` - Server URLs, paths, timeouts. Each server has an `id` mapped to folder `server_{id:02d}`
- `configs/server_01/` (and `server_02/`) contain per-server configs:
  - `action_config_advanced.json` - Action groups keyed by numeric ID
  - `auto_bot_loop_config.json` - Loop settings: stamina costs, boss order, PVP flags, cooldowns
  - `boss_config.json` - Boss metadata (union_id, name, level_limit)
  - `character_config.json` - Scraped character data (udid, level, etc.)
  - `account_config.json` - Login credentials (gitignored)
- `configs/all_stage_config.json` - Master list of stage names

`ServerConfigManager` loads server config and action configs. `AutoBotConfigManager` wraps `auto_bot_loop_config.json` with typed property accessors.

### Page Scraping

`scripts/battle_watcher_manager.py` parses raw HTML (not DOM) using regex to extract:
- Player stamina from `#mtime` span
- Boss cooldown from a specific text pattern
- Alive boss IDs from `onclick` attributes
- PVP rank info (detects if player is #1)

It also fetches the battle log page (`?ulog`) via HTTP requests to determine VIP boss respawn times.

### GUI

`start_up_window.py` is the entry point. Key classes:
- `LoginWindow` - Main window with server selector, start/stop/pause buttons, status labels
- `BotThread` (extends `QThread`) - Runs `HofAutoBot.run_once()` in a loop, supports pause/resume
- `CaptchaDialog` - Manual captcha input when auto-recognition fails
- `NormalBossOrderEditorDialog` - Visual reordering of normal boss priority list

The GUI manages a single `webdriver.Chrome` instance shared with the bot. On pause, `reload_configs()` is called so config changes take effect on resume.

### Logging

`scripts/log_manager.py` is a singleton (`LogManager.get_instance()`). Logs are written to `logs/log_server_{id}.txt` with newest entries at the top. Uses ANSI color codes for console output.

## Important Notes

- The bot scrapes HTML with regex, not a structured parser. Changes to the game's HTML structure will break `battle_watcher_manager.py` patterns.
- Auto-login uses OCR (Tesseract) on the captcha image with a character mapping file (`configs/captcha_map.json`). Tesseract must be installed separately.
- The bot adds random delays before boss challenges (`challenge_boss_delay_rate`) to avoid detection.
- Account credentials and character configs are gitignored.
- `.venv/` exists but is not gitignored explicitly; it's not in the repo.

## Behavioral Guidelines

Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
