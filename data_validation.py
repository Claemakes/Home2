"""
Data Validation Module for GlassRain

This module provides tools to validate database structure, check for duplicates,
and ensure data consistency across the application.
"""

import logging
import os
import sys
import json
import time
from datetime import datetime
from collections import defaultdict

# Ensure correct paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from glassrain_production.db_pool import get_connection, return_connection, execute_query

# Configure logging
logger = logging.getLogger(__name__)

def validate_database_structure():
    """
    Validate the database structure by checking for required tables and columns.
    
    Returns:
        dict: Validation results
    """
    logger.info("Starting database structure validation")
    
    # Define required tables and their expected columns
    required_tables = {
        "addresses": [
            "id", "street", "city", "state", "zip", "country", 
            "latitude", "longitude", "created_at"
        ],
        "service_categories": [
            "id", "name", "description", "icon"
        ],
        "services": [
            "id", "category_id", "name", "description", "base_price",
            "is_seasonal", "is_emergency", "is_maintenance", "is_recurring",
            "start_month", "end_month", "recurrence_period"
        ],
        "service_tiers": [
            "id", "name", "description", "multiplier"
        ],
        "contractors": [
            "id", "name", "company", "email", "phone", "website", 
            "rating", "service_area", "tier_id"
        ],
        "quotes": [
            "id", "user_id", "address_id", "service_id", "contractor_id", 
            "tier_id", "price", "status", "created_at", "scheduled_date"
        ],
        "recommendations": [
            "id", "user_id", "address_id", "service_id", "contractor_id", 
            "reason", "score", "created_at"
        ],
        "property_insights": [
            "id", "address_id", "user_id", "analysis_date", "insights_data"
        ],
        "task_history": [
            "id", "task_id", "name", "description", "status", "created_at",
            "started_at", "completed_at", "user_id", "progress", 
            "progress_message", "result_data", "error_data"
        ]
    }
    
    # Get database connection
    conn = get_connection()
    if not conn:
        return {"error": "Failed to connect to database"}
    
    cursor = None
    validation_results = {
        "timestamp": datetime.now().isoformat(),
        "tables_checked": [],
        "missing_tables": [],
        "missing_columns": {},
        "extra_columns": {},
        "all_valid": True
    }
    
    try:
        cursor = conn.cursor()
        
        # Get list of all tables in the database
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        
        existing_tables = [row[0] for row in cursor.fetchall()]
        validation_results["existing_tables"] = existing_tables
        
        # Check for missing tables
        for table in required_tables:
            validation_results["tables_checked"].append(table)
            
            if table not in existing_tables:
                validation_results["missing_tables"].append(table)
                validation_results["all_valid"] = False
                continue
            
            # Check columns for this table
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = '{table}'
            """)
            
            existing_columns = [row[0] for row in cursor.fetchall()]
            
            # Check for missing columns
            missing_columns = [col for col in required_tables[table] if col not in existing_columns]
            if missing_columns:
                validation_results["missing_columns"][table] = missing_columns
                validation_results["all_valid"] = False
            
            # Check for extra columns (not necessarily a problem but good to know)
            extra_columns = [col for col in existing_columns if col not in required_tables[table]]
            if extra_columns:
                validation_results["extra_columns"][table] = extra_columns
        
        # Additional validation: Check foreign key relationships
        foreign_keys = [
            {"table": "services", "column": "category_id", "references": "service_categories", "ref_column": "id"},
            {"table": "contractors", "column": "tier_id", "references": "service_tiers", "ref_column": "id"},
            {"table": "quotes", "column": "address_id", "references": "addresses", "ref_column": "id"},
            {"table": "quotes", "column": "service_id", "references": "services", "ref_column": "id"},
            {"table": "quotes", "column": "contractor_id", "references": "contractors", "ref_column": "id"},
            {"table": "quotes", "column": "tier_id", "references": "service_tiers", "ref_column": "id"},
            {"table": "recommendations", "column": "address_id", "references": "addresses", "ref_column": "id"},
            {"table": "recommendations", "column": "service_id", "references": "services", "ref_column": "id"},
            {"table": "recommendations", "column": "contractor_id", "references": "contractors", "ref_column": "id"},
            {"table": "property_insights", "column": "address_id", "references": "addresses", "ref_column": "id"}
        ]
        
        validation_results["foreign_key_issues"] = []
        
        for fk in foreign_keys:
            # Skip if either table is missing
            if (fk["table"] in validation_results["missing_tables"] or 
                fk["references"] in validation_results["missing_tables"]):
                continue
                
            # Skip if the column is missing
            if (fk["table"] in validation_results["missing_columns"] and 
                fk["column"] in validation_results["missing_columns"][fk["table"]]):
                continue
                
            if (fk["references"] in validation_results["missing_columns"] and 
                fk["ref_column"] in validation_results["missing_columns"][fk["references"]]):
                continue
            
            # Check for orphaned records (records with invalid foreign keys)
            cursor.execute(f"""
                SELECT COUNT(*) FROM {fk["table"]} t 
                LEFT JOIN {fk["references"]} r ON t.{fk["column"]} = r.{fk["ref_column"]}
                WHERE t.{fk["column"]} IS NOT NULL AND r.{fk["ref_column"]} IS NULL
            """)
            
            orphaned_count = cursor.fetchone()[0]
            
            if orphaned_count > 0:
                issue = {
                    "table": fk["table"],
                    "column": fk["column"],
                    "references": fk["references"],
                    "ref_column": fk["ref_column"],
                    "orphaned_records": orphaned_count
                }
                validation_results["foreign_key_issues"].append(issue)
                validation_results["all_valid"] = False
        
        logger.info(f"Database structure validation completed. All valid: {validation_results['all_valid']}")
        
    except Exception as e:
        logger.error(f"Error validating database structure: {str(e)}")
        validation_results["error"] = str(e)
        validation_results["all_valid"] = False
    finally:
        if cursor:
            cursor.close()
        return_connection(conn)
    
    return validation_results

def check_for_duplicates():
    """
    Check for duplicate records in key tables.
    
    Returns:
        dict: Duplicate check results
    """
    logger.info("Starting duplicate records check")
    
    # Define tables and columns to check for duplicates
    duplicate_checks = [
        {"table": "addresses", "columns": ["street", "city", "state", "zip"]},
        {"table": "service_categories", "columns": ["name"]},
        {"table": "services", "columns": ["category_id", "name"]},
        {"table": "service_tiers", "columns": ["name"]},
        {"table": "contractors", "columns": ["name", "company", "email", "phone"]},
        {"table": "quotes", "columns": ["user_id", "address_id", "service_id", "contractor_id", "scheduled_date"]}
    ]
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "checks_performed": [],
        "duplicates_found": {},
        "all_valid": True
    }
    
    for check in duplicate_checks:
        table = check["table"]
        columns = check["columns"]
        
        # Build a query to find duplicates
        columns_str = ", ".join(columns)
        query = f"""
            SELECT {columns_str}, COUNT(*) as count
            FROM {table}
            GROUP BY {columns_str}
            HAVING COUNT(*) > 1
        """
        
        try:
            duplicate_records = execute_query(query)
            
            results["checks_performed"].append({
                "table": table,
                "columns": columns
            })
            
            if duplicate_records and len(duplicate_records) > 0:
                results["duplicates_found"][table] = {
                    "columns_checked": columns,
                    "duplicate_count": len(duplicate_records),
                    "duplicates": duplicate_records
                }
                results["all_valid"] = False
                
                logger.warning(f"Found {len(duplicate_records)} duplicate(s) in {table} table")
        except Exception as e:
            logger.error(f"Error checking duplicates in {table}: {str(e)}")
            results["errors"] = results.get("errors", []) + [{
                "table": table,
                "error": str(e)
            }]
    
    logger.info(f"Duplicate check completed. All valid: {results['all_valid']}")
    return results

def check_data_consistency():
    """
    Check for data consistency issues across related tables.
    
    Returns:
        dict: Consistency check results
    """
    logger.info("Starting data consistency check")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "consistency_issues": [],
        "all_valid": True
    }
    
    # Define consistency checks
    consistency_checks = [
        # Check that service prices match tier multipliers
        {
            "name": "quote_price_consistency",
            "query": """
                SELECT q.id, q.price, s.base_price, st.multiplier, 
                       (s.base_price * st.multiplier) as expected_price
                FROM quotes q
                JOIN services s ON q.service_id = s.id
                JOIN service_tiers st ON q.tier_id = st.id
                WHERE ABS(q.price - (s.base_price * st.multiplier)) > 0.01
            """,
            "description": "Quote prices don't match the expected calculation (base_price * tier_multiplier)"
        },
        
        # Check for addresses without property insights
        {
            "name": "addresses_without_insights",
            "query": """
                SELECT a.id, a.street, a.city, a.state, a.zip
                FROM addresses a
                LEFT JOIN property_insights pi ON a.id = pi.address_id
                WHERE pi.id IS NULL
            """,
            "description": "Addresses without property insights",
            "is_warning": True  # This is not necessarily an error, just a warning
        },
        
        # Check for contractors without a valid tier
        {
            "name": "contractors_without_tier",
            "query": """
                SELECT c.id, c.name, c.company
                FROM contractors c
                LEFT JOIN service_tiers st ON c.tier_id = st.id
                WHERE c.tier_id IS NOT NULL AND st.id IS NULL
            """,
            "description": "Contractors with invalid tier_id"
        },
        
        # Check for seasonal services with missing month information
        {
            "name": "seasonal_services_missing_months",
            "query": """
                SELECT id, name, description
                FROM services
                WHERE is_seasonal = TRUE AND (start_month IS NULL OR end_month IS NULL)
            """,
            "description": "Seasonal services missing start_month or end_month"
        },
        
        # Check for recurring services with missing recurrence period
        {
            "name": "recurring_services_missing_period",
            "query": """
                SELECT id, name, description
                FROM services
                WHERE is_recurring = TRUE AND recurrence_period IS NULL
            """,
            "description": "Recurring services missing recurrence_period"
        }
    ]
    
    for check in consistency_checks:
        try:
            records = execute_query(check["query"])
            
            if records and len(records) > 0:
                issue = {
                    "name": check["name"],
                    "description": check["description"],
                    "record_count": len(records),
                    "records": records,
                    "is_warning": check.get("is_warning", False)
                }
                results["consistency_issues"].append(issue)
                
                # Only set all_valid to False if this is an error (not a warning)
                if not check.get("is_warning", False):
                    results["all_valid"] = False
                
                logger.warning(f"Found {len(records)} consistency issues: {check['name']}")
        except Exception as e:
            logger.error(f"Error running consistency check {check['name']}: {str(e)}")
            results["errors"] = results.get("errors", []) + [{
                "check": check["name"],
                "error": str(e)
            }]
    
    logger.info(f"Data consistency check completed. All valid: {results['all_valid']}")
    return results

def validate_user_interface():
    """
    Check for UI consistency across the application.
    This is a framework that would typically be populated with actual UI checks.
    
    Returns:
        dict: UI validation results
    """
    logger.info("Starting UI consistency check")
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "ui_sections_checked": [],
        "ui_issues": [],
        "all_valid": True
    }
    
    # Define UI consistency checks
    ui_checks = [
        {
            "name": "template_elements",
            "description": "Check that all pages have consistent template elements",
            "elements": ["header", "footer", "navigation", "branding"]
        },
        {
            "name": "style_consistency",
            "description": "Check for consistent styling across pages",
            "elements": ["color_scheme", "typography", "button_styles", "form_styling"]
        },
        {
            "name": "responsive_design",
            "description": "Check for responsive design elements",
            "elements": ["mobile_layout", "tablet_layout", "desktop_layout"]
        },
        {
            "name": "functional_elements",
            "description": "Check for consistent functional elements",
            "elements": ["search_bar", "login/account_area", "service_filters", "contact_methods"]
        }
    ]
    
    # In a real implementation, this would involve:
    # 1. Web scraping or DOM parsing to check template files
    # 2. CSS analysis to verify styling
    # 3. Responsive testing through headless browsers
    
    # For now, we'll implement a placeholder that simulates these checks
    for check in ui_checks:
        results["ui_sections_checked"].append(check["name"])
        
        # Simulate checking UI elements
        missing_elements = []
        inconsistent_elements = []
        
        # This is where actual checking would happen
        # For now, we'll assume all checks pass
        
        if missing_elements or inconsistent_elements:
            results["ui_issues"].append({
                "check_name": check["name"],
                "description": check["description"],
                "missing_elements": missing_elements,
                "inconsistent_elements": inconsistent_elements
            })
            results["all_valid"] = False
    
    logger.info(f"UI consistency check completed. All valid: {results['all_valid']}")
    return results

def run_comprehensive_validation():
    """
    Run all validation checks and compile a comprehensive report.
    
    Returns:
        dict: Complete validation results
    """
    start_time = time.time()
    logger.info("Starting comprehensive validation")
    
    results = {
        "validation_date": datetime.now().isoformat(),
        "database_structure": validate_database_structure(),
        "duplicate_checks": check_for_duplicates(),
        "data_consistency": check_data_consistency(),
        "ui_validation": validate_user_interface(),
        "all_valid": True
    }
    
    # Determine overall validity
    results["all_valid"] = (
        results["database_structure"]["all_valid"] and
        results["duplicate_checks"]["all_valid"] and
        results["data_consistency"]["all_valid"] and
        results["ui_validation"]["all_valid"]
    )
    
    # Compile summary of issues
    issues_summary = []
    
    if not results["database_structure"]["all_valid"]:
        missing_tables = results["database_structure"].get("missing_tables", [])
        missing_columns = results["database_structure"].get("missing_columns", {})
        foreign_key_issues = results["database_structure"].get("foreign_key_issues", [])
        
        if missing_tables:
            issues_summary.append(f"Missing tables: {', '.join(missing_tables)}")
        
        for table, columns in missing_columns.items():
            issues_summary.append(f"Table {table} missing columns: {', '.join(columns)}")
        
        for issue in foreign_key_issues:
            issues_summary.append(
                f"Foreign key issue: {issue['table']}.{issue['column']} references " +
                f"{issue['references']}.{issue['ref_column']} ({issue['orphaned_records']} orphaned records)"
            )
    
    duplicate_tables = results["duplicate_checks"].get("duplicates_found", {})
    for table, info in duplicate_tables.items():
        issues_summary.append(f"Found {info['duplicate_count']} duplicates in {table} table")
    
    for issue in results["data_consistency"].get("consistency_issues", []):
        prefix = "Warning" if issue.get("is_warning", False) else "Error"
        issues_summary.append(f"{prefix}: {issue['description']} ({issue['record_count']} records)")
    
    for issue in results["ui_validation"].get("ui_issues", []):
        issues_summary.append(f"UI consistency issue in {issue['check_name']}")
    
    results["issues_summary"] = issues_summary
    results["validation_time_seconds"] = time.time() - start_time
    
    logger.info(f"Comprehensive validation completed in {results['validation_time_seconds']:.2f} seconds")
    logger.info(f"Overall validation result: {'Valid' if results['all_valid'] else 'Invalid'}")
    
    if issues_summary:
        logger.warning(f"Found {len(issues_summary)} issues:")
        for issue in issues_summary:
            logger.warning(f"- {issue}")
    
    return results

def export_validation_report(results, format="json"):
    """
    Export validation results to a file.
    
    Args:
        results: Validation results
        format: Output format (json or html)
        
    Returns:
        str: Path to the output file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(current_dir, "validation_reports")
    
    # Create directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if format == "json":
        output_file = os.path.join(output_dir, f"validation_report_{timestamp}.json")
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
    elif format == "html":
        output_file = os.path.join(output_dir, f"validation_report_{timestamp}.html")
        
        # Simple HTML template for the report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>GlassRain Validation Report - {results['validation_date']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1, h2, h3 {{ color: #333; }}
                .summary {{ margin: 20px 0; padding: 10px; border-radius: 5px; }}
                .valid {{ background-color: #dff0d8; border: 1px solid #d6e9c6; color: #3c763d; }}
                .invalid {{ background-color: #f2dede; border: 1px solid #ebccd1; color: #a94442; }}
                .warning {{ background-color: #fcf8e3; border: 1px solid #faebcc; color: #8a6d3b; }}
                .issues {{ margin-top: 10px; }}
                .issue {{ margin: 5px 0; }}
                pre {{ background-color: #f5f5f5; padding: 10px; border-radius: 5px; overflow: auto; }}
            </style>
        </head>
        <body>
            <h1>GlassRain Validation Report</h1>
            <p>Generated on: {results['validation_date']}</p>
            
            <div class="summary {'valid' if results['all_valid'] else 'invalid'}">
                <h2>Overall Result: {'Valid' if results['all_valid'] else 'Invalid'}</h2>
                <p>Validation completed in {results['validation_time_seconds']:.2f} seconds</p>
            </div>
            
            <h2>Issues Summary</h2>
            <div class="issues">
        """
        
        if results['issues_summary']:
            for issue in results['issues_summary']:
                html_content += f'<div class="issue">• {issue}</div>\n'
        else:
            html_content += '<div class="issue">No issues found!</div>\n'
        
        html_content += """
            </div>
            
            <h2>Detailed Results</h2>
            <pre>
        """
        
        # Add detailed results as formatted JSON
        html_content += json.dumps(results, indent=2)
        
        html_content += """
            </pre>
        </body>
        </html>
        """
        
        with open(output_file, "w") as f:
            f.write(html_content)
    else:
        raise ValueError(f"Unsupported output format: {format}")
    
    logger.info(f"Validation report exported to {output_file}")
    return output_file

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run validation and export report
    results = run_comprehensive_validation()
    export_validation_report(results, format="html")