# Discord Image Poll Bot

A custom Discord bot that allows server administrators to create large-scale image polls (up to 50 images). Unlike native Discord polls, this bot handles dozens of options by displaying each image individually with dedicated voting buttons. 

Results are hidden while the poll is active, and the Top 10 winners are revealed when the poll is closed.

## Features

- **Up to 50 Images:** Create massive polls by uploading a simple text file of image URLs.
- **Custom Max Picks:** Set a limit on how many different images a single user can vote for (e.g., "Pick your top 3").
- **Swipe & Vote UX:** Each photo is displayed as a separate message with a toggleable "Vote" button.
- **Blind Voting:** Live results are completely hidden from users until the poll is concluded.
- **Winner Reveal:** Closing the poll generates a Top 10 leaderboard with medals (🥇 🥈 🥉) and bar charts.
- **Smart URL Parsing:** Automatically fixes generic Imgur links to direct image links so they embed properly in Discord.

## Prerequisites

- Python 3.9 or higher
- A Discord Bot Token

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/YOUR-USERNAME/discord-poll-bot.git
   cd discord-poll-bot
   ```

2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Set your Discord Bot Token as an environment variable:
   - **Windows (PowerShell):**
     ```powershell
     $env:DISCORD_BOT_TOKEN="your_bot_token_here"
     ```
   - **Mac/Linux:**
     ```bash
     export DISCORD_BOT_TOKEN="your_bot_token_here"
     ```

## Usage

1. Start the bot:
   ```bash
   python bot.py
   ```

2. Invite the bot to your Discord server (ensure it has permissions to Send Messages, Embed Links, Attach Files, and use Application Commands).

3. Create a text file (e.g., `images.txt`) containing the direct URLs of the images you want in the poll, one URL per line.

4. In your Discord server, use the slash command:
   ```
   /createpoll title:"Best Artwork" max_picks:3 images:[Attach your images.txt file]
   ```

## Commands

- `/createpoll` - Create a new poll (requires an attached `.txt` file of URLs).
- `/closepoll <poll_id>` - Close an active poll and reveal the Top 10 winners (Admin/Creator only).
- `/myvotes <poll_id>` - See which options you have currently voted for.
- `/deletepoll <poll_id>` - Delete a poll and all of its associated data (Admin/Creator only).
- `/results <poll_id>` - View the results of a closed poll.

## Security Note

Your bot token is securely loaded from your environment variables. **Never commit your Discord token directly into the code.**
