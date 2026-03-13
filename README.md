# quota-watch-cli

CLI tool to monitor and alert on quota usage for directories. Built this because I kept running out of disk space and wanted something simple to track usage before things blow up.

## Why

- Monitor directory sizes against defined quotas
- Get warnings before you hit 100%
- Track file counts too (useful for maildirs, log rotation, etc.)
- Simple JSON config, easy to version control
- Exit codes work great with cron and monitoring systems

## Install

No dependencies beyond Python 3.6+. Just clone and run:

```bash
python3 quota_watch.py --help
```

Or make it executable and drop it in your PATH:

```bash
chmod +x quota_watch.py
cp quota_watch.py ~/bin/quota-watch
```

## Quick Start

```bash
# Create a sample config
quota-watch init

# Edit quota_config.json to set your paths and limits

# Check all quotas
quota-watch check

# See disk usage for a path
quota-watch disk /home/user
```

## Commands

### init

Creates a sample `quota_config.json` with a couple example rules. Good starting point.

```bash
quota-watch init
quota-watch init -c /etc/quota-watch/config.json
```

### add

Add a new quota rule:

```bash
quota-watch add /var/log -m 500 -n "log_directory"
quota-watch add /tmp -m 1000 -f 50000 -t 0.9
```

Options:
- `-m, --max-size`: Maximum size in MB (required)
- `-f, --max-files`: Maximum file count (optional)
- `-t, --threshold`: Alert threshold 0-1, default 0.8 (80%)
- `-n, --name`: Friendly name for the rule
- `-c, --config`: Config file path

### check

Run all quota checks and print a status table:

```bash
quota-watch check
quota-watch check -c /path/to/config.json
```

Output in JSON format:

```bash
quota-watch check --format json
```

Exit codes:
- `0`: All OK
- `1`: Warnings found
- `2`: Critical (quota exceeded)

Perfect for cron jobs and monitoring systems like Nagios or Prometheus blackbox exporter.

### list

Show all configured quotas:

```bash
quota-watch list
```

### remove

Delete a quota rule by path or name:

```bash
quota-watch remove /var/log
```

### disk

Quick disk space check for any path:

```bash
quota-watch disk
quota-watch disk /home
```

## Config Format

JSON file with a `quotas` array:

```json
{
  "quotas": [
    {
      "name": "log_directory",
      "path": "/var/log",
      "max_size_mb": 500,
      "max_files": 10000,
      "alert_threshold": 0.8
    },
    {
      "path": "/tmp",
      "max_size_mb": 1000
    }
  ]
}
```

Fields:
- `path`: Directory to monitor (required)
- `max_size_mb`: Size limit in MB (required)
- `max_files`: File count limit (optional)
- `alert_threshold`: When to warn (0-1, default 0.8)
- `name`: Friendly name, defaults to path

## Cron Example

Add to crontab for daily checks:

```cron
0 9 * * * /usr/local/bin/quota-watch check -c /etc/quota-watch/config.json || mail -s "Quota Alert" admin@example.com
```

Or use with a monitoring system that checks exit codes.

## Notes

- Symlinks are not followed (won't double-count files)
- Permission errors are logged but don't fail the check
- File sizes are calculated recursively
- Uses MB (1024*1024 bytes) for consistency

## License

MIT - do whatever you want with it.
