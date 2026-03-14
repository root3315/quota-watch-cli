#!/usr/bin/env python3
"""
quota-watch-cli: Monitor and alert on quota usage for directories and files.
"""

import argparse
import json
import os
import shutil
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class QuotaConfig:
    """Configuration for a single quota rule."""
    path: str
    max_size_mb: float
    max_files: Optional[int] = None
    alert_threshold: float = 0.8
    name: Optional[str] = None


@dataclass
class QuotaStatus:
    """Current status of a quota rule."""
    name: str
    path: str
    current_size_mb: float
    current_files: int
    max_size_mb: float
    max_files: Optional[int]
    usage_percent: float
    file_usage_percent: Optional[float]
    status: str
    alerts: List[str]


def get_directory_size(path: str) -> tuple:
    """Calculate total size in MB and file count for a directory."""
    total_size = 0
    file_count = 0
    
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    if not os.path.islink(filepath):
                        total_size += os.path.getsize(filepath)
                        file_count += 1
                except (OSError, IOError):
                    continue
    except (OSError, IOError) as e:
        print(f"Warning: Could not scan {path}: {e}", file=sys.stderr)
    
    size_mb = total_size / (1024 * 1024)
    return size_mb, file_count


def check_quota(config: QuotaConfig) -> QuotaStatus:
    """Check quota status for a single rule."""
    name = config.name or config.path
    current_size, current_files = get_directory_size(config.path)
    
    usage_percent = (current_size / config.max_size_mb) * 100 if config.max_size_mb > 0 else 0
    
    file_usage_percent = None
    if config.max_files is not None and config.max_files > 0:
        file_usage_percent = (current_files / config.max_files) * 100
    
    alerts = []
    status = "OK"
    
    if usage_percent >= 100:
        status = "CRITICAL"
        alerts.append(f"Size quota exceeded: {current_size:.2f}MB / {config.max_size_mb}MB")
    elif usage_percent >= config.alert_threshold * 100:
        status = "WARNING"
        alerts.append(f"Size quota warning: {current_size:.2f}MB / {config.max_size_mb}MB ({usage_percent:.1f}%)")
    
    if config.max_files is not None:
        if file_usage_percent >= 100:
            status = "CRITICAL"
            alerts.append(f"File count quota exceeded: {current_files} / {config.max_files}")
        elif file_usage_percent >= config.alert_threshold * 100 and status != "CRITICAL":
            status = "WARNING"
            alerts.append(f"File count warning: {current_files} / {config.max_files} ({file_usage_percent:.1f}%)")
    
    return QuotaStatus(
        name=name,
        path=config.path,
        current_size_mb=current_size,
        current_files=current_files,
        max_size_mb=config.max_size_mb,
        max_files=config.max_files,
        usage_percent=usage_percent,
        file_usage_percent=file_usage_percent,
        status=status,
        alerts=alerts
    )


def load_config(config_path: str) -> List[QuotaConfig]:
    """Load quota configuration from JSON file."""
    with open(config_path, 'r') as f:
        data = json.load(f)
    
    configs = []
    for item in data.get('quotas', []):
        configs.append(QuotaConfig(
            path=item['path'],
            max_size_mb=item['max_size_mb'],
            max_files=item.get('max_files'),
            alert_threshold=item.get('alert_threshold', 0.8),
            name=item.get('name')
        ))
    return configs


def save_config(configs: List[QuotaConfig], config_path: str) -> None:
    """Save quota configuration to JSON file."""
    data = {'quotas': [asdict(c) for c in configs]}
    with open(config_path, 'w') as f:
        json.dump(data, f, indent=2)


def format_status_table(statuses: List[QuotaStatus]) -> str:
    """Format quota statuses as a table."""
    if not statuses:
        return "No quotas configured."
    
    lines = []
    header = f"{'NAME':<25} {'STATUS':<10} {'SIZE':<20} {'FILES':<15} {'USAGE':<10}"
    separator = "-" * len(header)
    
    lines.append(header)
    lines.append(separator)
    
    for s in statuses:
        size_str = f"{s.current_size_mb:.1f}/{s.max_size_mb:.0f}MB"
        files_str = f"{s.current_files}" if s.max_files else f"{s.current_files}/-"
        usage_str = f"{s.usage_percent:.1f}%"
        
        lines.append(f"{s.name:<25} {s.status:<10} {size_str:<20} {files_str:<15} {usage_str:<10}")
        
        for alert in s.alerts:
            lines.append(f"  -> {alert}")
    
    return "\n".join(lines)


def check_disk_space(path: str) -> tuple:
    """Check available disk space for a path."""
    try:
        total, used, free = shutil.disk_usage(path)
        total_gb = total / (1024 ** 3)
        used_gb = used / (1024 ** 3)
        free_gb = free / (1024 ** 3)
        usage_pct = (used / total) * 100
        return total_gb, used_gb, free_gb, usage_pct
    except OSError as e:
        return None, None, None, None


def cmd_check(args):
    """Handle the check command."""
    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    
    configs = load_config(args.config)
    statuses = [check_quota(config) for config in configs]
    
    print(format_status_table(statuses))
    
    critical_count = sum(1 for s in statuses if s.status == "CRITICAL")
    warning_count = sum(1 for s in statuses if s.status == "WARNING")
    
    print()
    print(f"Summary: {critical_count} critical, {warning_count} warnings, {len(statuses)} total")
    
    if critical_count > 0:
        sys.exit(2)
    elif warning_count > 0:
        sys.exit(1)
    sys.exit(0)


def cmd_add(args):
    """Handle the add command."""
    configs = []
    if os.path.exists(args.config):
        configs = load_config(args.config)
    
    name = args.name if args.name else args.path
    new_config = QuotaConfig(
        path=args.path,
        max_size_mb=args.max_size,
        max_files=args.max_files,
        alert_threshold=args.threshold,
        name=name
    )
    configs.append(new_config)
    save_config(configs, args.config)
    print(f"Added quota rule: {name}")
    print(f"  Path: {args.path}")
    print(f"  Max Size: {args.max_size}MB")
    if args.max_files:
        print(f"  Max Files: {args.max_files}")
    print(f"  Alert Threshold: {args.threshold * 100}%")


def cmd_remove(args):
    """Handle the remove command."""
    if not os.path.exists(args.config):
        print(f"Error: Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    
    configs = load_config(args.config)
    original_count = len(configs)
    configs = [c for c in configs if c.path != args.path and c.name != args.path]
    
    if len(configs) == original_count:
        print(f"No quota rule found for: {args.path}")
        sys.exit(1)
    
    save_config(configs, args.config)
    print(f"Removed quota rule: {args.path}")


def cmd_list(args):
    """Handle the list command."""
    if not os.path.exists(args.config):
        print("No configuration file found.")
        return
    
    configs = load_config(args.config)
    if not configs:
        print("No quotas configured.")
        return
    
    print("Configured Quotas:")
    print("-" * 50)
    for i, config in enumerate(configs, 1):
        name = config.name or config.path
        print(f"{i}. {name}")
        print(f"   Path: {config.path}")
        print(f"   Max Size: {config.max_size_mb}MB")
        if config.max_files:
            print(f"   Max Files: {config.max_files}")
        print(f"   Alert at: {config.alert_threshold * 100}%")
        print()


def cmd_init(args):
    """Handle the init command."""
    if os.path.exists(args.config):
        print(f"Error: Config file already exists: {args.config}", file=sys.stderr)
        sys.exit(1)
    
    sample_configs = [
        QuotaConfig(path="/tmp", max_size_mb=1000, name="temp_directory"),
        QuotaConfig(path=os.path.expanduser("~"), max_size_mb=5000, max_files=100000, name="home_directory"),
    ]
    save_config(sample_configs, args.config)
    print(f"Created sample configuration: {args.config}")
    print("Edit this file to customize your quota rules.")


def cmd_disk(args):
    """Handle the disk command."""
    path = args.path or "."
    total, used, free, usage_pct = check_disk_space(path)
    
    if total is None:
        print(f"Error: Could not get disk info for: {path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Disk Usage for: {os.path.abspath(path)}")
    print("-" * 40)
    print(f"Total:     {total:.2f} GB")
    print(f"Used:      {used:.2f} GB")
    print(f"Free:      {free:.2f} GB")
    print(f"Usage:     {usage_pct:.1f}%")
    
    bar_width = 30
    filled = int(bar_width * usage_pct / 100)
    bar = "[" + "#" * filled + "-" * (bar_width - filled) + "]"
    print(f"           {bar}")


def main():
    parser = argparse.ArgumentParser(
        prog='quota-watch',
        description='Monitor and alert on quota usage for directories'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    check_parser = subparsers.add_parser('check', help='Check all quota rules')
    check_parser.add_argument('-c', '--config', default='quota_config.json',
                              help='Path to config file (default: quota_config.json)')
    check_parser.set_defaults(func=cmd_check)
    
    add_parser = subparsers.add_parser('add', help='Add a new quota rule')
    add_parser.add_argument('path', help='Directory path to monitor')
    add_parser.add_argument('-m', '--max-size', type=float, required=True,
                            help='Maximum size in MB')
    add_parser.add_argument('-f', '--max-files', type=int, default=None,
                            help='Maximum file count (optional)')
    add_parser.add_argument('-t', '--threshold', type=float, default=0.8,
                            help='Alert threshold 0-1 (default: 0.8)')
    add_parser.add_argument('-n', '--name', default=None,
                            help='Rule name (default: path)')
    add_parser.add_argument('-c', '--config', default='quota_config.json',
                            help='Path to config file')
    add_parser.set_defaults(func=cmd_add)
    
    remove_parser = subparsers.add_parser('remove', help='Remove a quota rule')
    remove_parser.add_argument('path', help='Path or name of rule to remove')
    remove_parser.add_argument('-c', '--config', default='quota_config.json',
                               help='Path to config file')
    remove_parser.set_defaults(func=cmd_remove)
    
    list_parser = subparsers.add_parser('list', help='List all quota rules')
    list_parser.add_argument('-c', '--config', default='quota_config.json',
                             help='Path to config file')
    list_parser.set_defaults(func=cmd_list)
    
    init_parser = subparsers.add_parser('init', help='Initialize config file')
    init_parser.add_argument('-c', '--config', default='quota_config.json',
                             help='Path to config file')
    init_parser.set_defaults(func=cmd_init)
    
    disk_parser = subparsers.add_parser('disk', help='Show disk usage info')
    disk_parser.add_argument('path', nargs='?', default=None,
                             help='Path to check (default: current directory)')
    disk_parser.set_defaults(func=cmd_disk)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        sys.exit(0)
    
    args.func(args)


if __name__ == '__main__':
    main()
