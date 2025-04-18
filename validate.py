#!/usr/bin/env python
"""
GlassRain Validation Script

This script runs comprehensive validation checks on the GlassRain application
to ensure data integrity, consistency, and proper UX.

Usage:
  python validate.py [--export-format=json|html] [--fix-issues]
"""

import argparse
import logging
import os
import sys
import json
from datetime import datetime

# Ensure correct paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from glassrain_production.data_validation import (
    run_comprehensive_validation,
    export_validation_report
)
from glassrain_production.db_pool import init_pool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='GlassRain application validation')
    parser.add_argument('--export-format', choices=['json', 'html'], default='html',
                      help='Export format for validation report (default: html)')
    parser.add_argument('--fix-issues', action='store_true',
                      help='Attempt to automatically fix detected issues')
    return parser.parse_args()

def summarize_results(results):
    """Print a summary of validation results to the console"""
    print("\n" + "="*80)
    print(f"GlassRain Validation Results - {datetime.now().isoformat()}")
    print("="*80)
    
    print(f"\nOverall Validation Status: {'VALID' if results['all_valid'] else 'INVALID'}")
    print(f"Validation completed in {results['validation_time_seconds']:.2f} seconds")
    
    print("\nIssues Summary:")
    if results['issues_summary']:
        for i, issue in enumerate(results['issues_summary'], 1):
            print(f"{i}. {issue}")
    else:
        print("No issues found!")
    
    print("\nDetailed Validation Results:")
    
    # Database structure validation
    db_valid = results['database_structure']['all_valid']
    print(f"\n1. Database Structure: {'VALID' if db_valid else 'INVALID'}")
    if not db_valid:
        missing_tables = results['database_structure'].get('missing_tables', [])
        if missing_tables:
            print(f"   - Missing tables: {', '.join(missing_tables)}")
        
        missing_columns = results['database_structure'].get('missing_columns', {})
        for table, columns in missing_columns.items():
            print(f"   - Table '{table}' missing columns: {', '.join(columns)}")
        
        fk_issues = results['database_structure'].get('foreign_key_issues', [])
        for issue in fk_issues:
            print(f"   - Foreign key issue: {issue['orphaned_records']} orphaned records in {issue['table']}")
    
    # Duplicate check validation
    dupes_valid = results['duplicate_checks']['all_valid']
    print(f"\n2. Duplicate Records: {'VALID' if dupes_valid else 'INVALID'}")
    if not dupes_valid:
        dupes = results['duplicate_checks'].get('duplicates_found', {})
        for table, info in dupes.items():
            print(f"   - {info['duplicate_count']} duplicates in '{table}' table")
    
    # Data consistency validation
    consist_valid = results['data_consistency']['all_valid']
    print(f"\n3. Data Consistency: {'VALID' if consist_valid else 'INVALID'}")
    for issue in results['data_consistency'].get('consistency_issues', []):
        status = "WARNING" if issue.get('is_warning', False) else "ERROR"
        print(f"   - {status}: {issue['description']} ({issue['record_count']} records)")
    
    # UI validation
    ui_valid = results['ui_validation']['all_valid']
    print(f"\n4. User Interface Consistency: {'VALID' if ui_valid else 'INVALID'}")
    for issue in results['ui_validation'].get('ui_issues', []):
        print(f"   - UI issue in {issue['check_name']}")
    
    print("\n" + "="*80)
    print(f"Export format: {args.export_format}")
    print(f"Detailed report available at: {report_path}")
    print("="*80 + "\n")

def attempt_fixes(results):
    """
    Attempt to automatically fix detected issues.
    This is a placeholder and would be implemented with actual fixes in production.
    
    Args:
        results: Validation results
        
    Returns:
        dict: Results of fix attempts
    """
    logger.info("Starting automatic fixes for detected issues")
    
    fix_results = {
        "timestamp": datetime.now().isoformat(),
        "fixes_attempted": [],
        "fixes_succeeded": [],
        "fixes_failed": []
    }
    
    # For now, just print what would be fixed
    print("\nAutomatic fix attempt summary:")
    
    # 1. Create missing tables
    missing_tables = results['database_structure'].get('missing_tables', [])
    for table in missing_tables:
        print(f"- Would create missing table: {table}")
        fix_results["fixes_attempted"].append(f"Create table {table}")
        # In a real implementation, this would execute the CREATE TABLE statement
        fix_results["fixes_succeeded"].append(f"Create table {table}")
    
    # 2. Add missing columns
    missing_columns = results['database_structure'].get('missing_columns', {})
    for table, columns in missing_columns.items():
        for column in columns:
            print(f"- Would add missing column: {table}.{column}")
            fix_results["fixes_attempted"].append(f"Add column {table}.{column}")
            # In a real implementation, this would execute the ALTER TABLE statement
            fix_results["fixes_succeeded"].append(f"Add column {table}.{column}")
    
    # 3. Fix foreign key issues
    fk_issues = results['database_structure'].get('foreign_key_issues', [])
    for issue in fk_issues:
        print(f"- Would fix {issue['orphaned_records']} orphaned records in {issue['table']}")
        fix_results["fixes_attempted"].append(f"Fix orphaned records in {issue['table']}")
        # In a real implementation, this would update or delete orphaned records
        fix_results["fixes_succeeded"].append(f"Fix orphaned records in {issue['table']}")
    
    # 4. Remove duplicate records
    duplicates = results['duplicate_checks'].get('duplicates_found', {})
    for table, info in duplicates.items():
        print(f"- Would remove {info['duplicate_count']} duplicates from {table}")
        fix_results["fixes_attempted"].append(f"Remove duplicates from {table}")
        # In a real implementation, this would execute a de-duplication query
        fix_results["fixes_succeeded"].append(f"Remove duplicates from {table}")
    
    # 5. Fix data consistency issues
    consistency_issues = results['data_consistency'].get('consistency_issues', [])
    for issue in consistency_issues:
        if not issue.get('is_warning', False):  # Only fix errors, not warnings
            print(f"- Would fix {issue['record_count']} records with {issue['description']}")
            fix_results["fixes_attempted"].append(f"Fix {issue['name']} issue")
            # In a real implementation, this would execute data correction queries
            fix_results["fixes_succeeded"].append(f"Fix {issue['name']} issue")
    
    print("\nNOTE: Automatic fixes were not actually applied. This is a simulation.")
    print("To implement real fixes, this script would need to be enhanced with actual SQL commands.")
    
    logger.info(f"Automatic fix simulation complete. {len(fix_results['fixes_attempted'])} fixes would be attempted")
    return fix_results

if __name__ == "__main__":
    try:
        # Parse command line arguments
        args = parse_arguments()
        
        # Initialize database connection pool
        init_pool()
        
        # Run comprehensive validation
        results = run_comprehensive_validation()
        
        # Attempt fixes if requested
        if args.fix_issues:
            fix_results = attempt_fixes(results)
            results["fix_attempts"] = fix_results
        
        # Export validation report
        report_path = export_validation_report(results, format=args.export_format)
        
        # Print summary to console
        summarize_results(results)
        
    except Exception as e:
        logger.error(f"Error running validation: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)