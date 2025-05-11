# Metropolis Parking Receipts Downloader

This script automates the process of downloading parking receipts from Metropolis for a specific month.

## Prerequisites

1. Clone this repository or download the script
2. Install required packages:

```bash
pip install -r requirements.txt
```

### Using Micromamba (Recommended)

If you're using micromamba, you can run the script in a dedicated environment:

```bash
# Create and activate the environment
micromamba create -n parking-receipts python=3.11
micromamba activate parking-receipts

# Install dependencies
pip install -r requirements.txt

# Run the script in the environment
python metropolis_receipts.py <month>
```

## Authentication

The script handles authentication in the following ways:

1. **First-time use**: You'll be prompted to log in manually with your phone number and the verification code sent to you.
2. **Subsequent use**: The script saves your authentication cookies to `metropolis_cookies.json` and will reuse them automatically.
3. **Force re-login**: If you encounter authentication issues, use the `--force-login` flag to perform a new manual login.

The script respects your privacy by storing cookies only on your local machine.

## Usage

### Basic Usage

Run the script with the month you want to download receipts for:

```bash
python metropolis_receipts.py <month>
```

For example:
```bash
python metropolis_receipts.py april
```

By default, receipts will be saved to `~/Documents/parking-receipts/<month>/`.

### Advanced Options

The script provides several command-line options for customization:

```bash
python metropolis_receipts.py <month> [options]
```

Available options:

| Option | Description |
|--------|-------------|
| `--output-dir`, `-o` | Specify the root directory to store receipts (default: `~/Documents/parking-receipts`) |
| `--browser` | Choose the browser to use for automation: `chrome` (default) or `firefox` |
| `--force-login` | Force manual login even if cookies exist |

### Examples

#### Save receipts to a custom directory:
```bash
python metropolis_receipts.py april -o ~/Desktop/receipts
```

#### Use Firefox instead of Chrome:
```bash
python metropolis_receipts.py april --browser firefox
```

#### Force a new login (useful if saved cookies expire):
```bash
python metropolis_receipts.py april --force-login
```

#### Combine multiple options:
```bash
python metropolis_receipts.py april -o ~/Desktop/receipts --browser firefox --force-login
```

## How It Works

1. The script logs into your Metropolis account (either using saved cookies or manual login)
2. It fetches your visit history for the specified month
3. It downloads PDF receipts for each visit
4. All receipts are saved to the specified output directory

