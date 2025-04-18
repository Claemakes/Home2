"""
UX Consistency Validator for GlassRain

This module checks for consistency across HTML templates and UI elements
to ensure a unified user experience across the application.
"""

import logging
import os
import re
import glob
import json
from datetime import datetime
from collections import defaultdict
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger(__name__)

class UXValidator:
    """UX Validation class to check for UI consistency across templates"""
    
    def __init__(self, templates_dir=None):
        """
        Initialize the UX validator.
        
        Args:
            templates_dir: Directory containing HTML templates
        """
        self.templates_dir = templates_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'templates'
        )
        
        # Expected common elements across templates
        self.expected_common_elements = {
            "header": ["header", "nav", ".navbar"],
            "footer": ["footer", ".footer"],
            "branding": [".logo", "img.logo", ".brand"],
            "navigation": ["nav", ".nav", ".navigation", "ul.menu"],
            "search": ["input[type=search]", ".search", "form.search"]
        }
        
        # Expected ARIA attributes for accessibility
        self.expected_aria_attributes = {
            "button": ["aria-label", "aria-pressed"],
            "input": ["aria-label", "aria-required"],
            "a": ["aria-label", "aria-current"],
            "nav": ["aria-label"],
            "div[role=dialog]": ["aria-labelledby", "aria-modal"]
        }
        
        # Expected CSS classes for styling consistency
        self.expected_css_classes = {
            "buttons": ["btn", "button"],
            "forms": ["form-group", "form-control"],
            "cards": ["card"],
            "containers": ["container", "wrapper"],
            "alerts": ["alert", "notification"],
            "modals": ["modal"]
        }
        
        # Color schemes and design tokens we expect to be used
        self.design_tokens = {
            "colors": ["#333333", "#ffffff", "#007bff", "#28a745", "#dc3545", "#ffc107", "#17a2b8"],
            "fonts": ["Arial", "sans-serif", "Helvetica", "Roboto"],
            "sizes": ["px", "rem", "em", "%", "vh", "vw"]
        }
    
    def get_template_files(self):
        """
        Get all HTML template files from the templates directory.
        
        Returns:
            list: List of HTML file paths
        """
        template_pattern = os.path.join(self.templates_dir, "**", "*.html")
        return glob.glob(template_pattern, recursive=True)
    
    def parse_html_template(self, template_path):
        """
        Parse an HTML template file using BeautifulSoup.
        
        Args:
            template_path: Path to the template file
            
        Returns:
            BeautifulSoup: Parsed HTML or None if parsing failed
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            return soup
        except Exception as e:
            logger.error(f"Error parsing template {template_path}: {str(e)}")
            return None
    
    def check_common_elements(self, soup, template_name):
        """
        Check if template contains expected common elements.
        
        Args:
            soup: BeautifulSoup parsed template
            template_name: Template name for reporting
            
        Returns:
            dict: Check results
        """
        results = {
            "template": template_name,
            "missing_elements": [],
            "found_elements": []
        }
        
        for element_name, selectors in self.expected_common_elements.items():
            found = False
            
            # Try each selector until we find a match
            for selector in selectors:
                if selector.startswith('.'):
                    # Class selector
                    elements = soup.select(selector)
                    if elements:
                        found = True
                        break
                elif selector.startswith('#'):
                    # ID selector
                    elements = soup.select(selector)
                    if elements:
                        found = True
                        break
                else:
                    # Tag name
                    elements = soup.find_all(selector)
                    if elements:
                        found = True
                        break
            
            if found:
                results["found_elements"].append(element_name)
            else:
                results["missing_elements"].append(element_name)
        
        return results
    
    def check_accessibility(self, soup, template_name):
        """
        Check if template contains expected accessibility attributes.
        
        Args:
            soup: BeautifulSoup parsed template
            template_name: Template name for reporting
            
        Returns:
            dict: Check results
        """
        results = {
            "template": template_name,
            "accessibility_issues": []
        }
        
        for selector, expected_attrs in self.expected_aria_attributes.items():
            elements = soup.select(selector)
            
            for element in elements:
                missing_attrs = []
                
                for attr in expected_attrs:
                    if not element.has_attr(attr):
                        missing_attrs.append(attr)
                
                if missing_attrs:
                    # Build a simple representation of the element for reporting
                    element_str = element.name
                    if element.has_attr('id'):
                        element_str += f'#{element["id"]}'
                    elif element.has_attr('class'):
                        classes = ' '.join(element['class'])
                        element_str += f'.{classes.replace(" ", ".")}'
                    
                    results["accessibility_issues"].append({
                        "element": element_str,
                        "missing_attributes": missing_attrs
                    })
        
        return results
    
    def check_css_consistency(self, soup, template_name):
        """
        Check if template contains expected CSS classes for consistent styling.
        
        Args:
            soup: BeautifulSoup parsed template
            template_name: Template name for reporting
            
        Returns:
            dict: Check results
        """
        results = {
            "template": template_name,
            "css_issues": []
        }
        
        # Check for each element type
        element_mapping = {
            "buttons": ["button", "a.btn", "input[type=button]", "input[type=submit]"],
            "forms": ["form", "input", "textarea", "select"],
            "cards": ["div.card", ".card"],
            "containers": ["div.container", "div.wrapper", ".container", ".wrapper"],
            "alerts": [".alert", ".notification"],
            "modals": [".modal", "div[role=dialog]"]
        }
        
        for element_type, selectors in element_mapping.items():
            expected_classes = self.expected_css_classes[element_type]
            
            for selector in selectors:
                elements = soup.select(selector)
                
                for element in elements:
                    if not element.has_attr('class'):
                        results["css_issues"].append({
                            "element_type": element_type,
                            "element": str(element)[:100],  # First 100 chars for brevity
                            "issue": "Missing class attribute"
                        })
                        continue
                    
                    # Check if any of the expected classes is present
                    found_expected_class = False
                    for expected_class in expected_classes:
                        if expected_class in element['class']:
                            found_expected_class = True
                            break
                    
                    if not found_expected_class:
                        results["css_issues"].append({
                            "element_type": element_type,
                            "element": str(element)[:100],  # First 100 chars for brevity
                            "issue": f"None of the expected classes found: {expected_classes}"
                        })
        
        return results
    
    def check_color_consistency(self, soup, template_name):
        """
        Check if template uses consistent colors based on design tokens.
        
        Args:
            soup: BeautifulSoup parsed template
            template_name: Template name for reporting
            
        Returns:
            dict: Check results
        """
        results = {
            "template": template_name,
            "color_issues": []
        }
        
        # Extract inline styles
        elements_with_style = soup.select('[style]')
        
        for element in elements_with_style:
            style = element['style']
            
            # Extract colors from inline styles
            color_matches = re.findall(r'color:\s*(#[0-9a-fA-F]{3,6}|rgb\([^)]+\)|rgba\([^)]+\))', style)
            bg_color_matches = re.findall(r'background(-color)?:\s*(#[0-9a-fA-F]{3,6}|rgb\([^)]+\)|rgba\([^)]+\))', style)
            
            all_colors = color_matches + [m[1] for m in bg_color_matches if len(m) > 1]
            
            # Check if colors match our design tokens
            for color in all_colors:
                if color.lower() not in [c.lower() for c in self.design_tokens["colors"]]:
                    results["color_issues"].append({
                        "element": str(element)[:100],  # First 100 chars for brevity
                        "color": color,
                        "issue": "Color not in design tokens"
                    })
        
        return results
    
    def check_responsive_design(self, soup, template_name):
        """
        Check if template contains responsive design elements.
        
        Args:
            soup: BeautifulSoup parsed template
            template_name: Template name for reporting
            
        Returns:
            dict: Check results
        """
        results = {
            "template": template_name,
            "responsive_issues": []
        }
        
        # Check for viewport meta tag
        viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
        if not viewport_meta:
            results["responsive_issues"].append({
                "issue": "Missing viewport meta tag"
            })
        
        # Check for responsive classes (Bootstrap or similar)
        responsive_classes = ["container-fluid", "row", "col", "col-sm", "col-md", "col-lg", "col-xl"]
        found_responsive_classes = False
        
        for element in soup.find_all(class_=True):
            for cls in element['class']:
                if any(cls.startswith(rc) for rc in responsive_classes):
                    found_responsive_classes = True
                    break
            
            if found_responsive_classes:
                break
        
        if not found_responsive_classes:
            results["responsive_issues"].append({
                "issue": "No responsive grid classes found"
            })
        
        # Check for media queries in embedded styles
        style_tags = soup.find_all('style')
        found_media_queries = False
        
        for style_tag in style_tags:
            if '@media' in style_tag.string:
                found_media_queries = True
                break
        
        if not found_media_queries and style_tags:
            results["responsive_issues"].append({
                "issue": "No media queries found in embedded styles"
            })
        
        return results
    
    def validate_templates(self):
        """
        Validate all templates for UX consistency.
        
        Returns:
            dict: Validation results
        """
        logger.info("Starting UX template validation")
        
        template_files = self.get_template_files()
        
        if not template_files:
            logger.warning(f"No template files found in {self.templates_dir}")
            return {
                "error": f"No template files found in {self.templates_dir}",
                "all_valid": False
            }
        
        results = {
            "templates_checked": [],
            "templates_with_issues": [],
            "common_elements_check": [],
            "accessibility_check": [],
            "css_consistency_check": [],
            "color_consistency_check": [],
            "responsive_design_check": [],
            "all_valid": True
        }
        
        for template_file in template_files:
            template_name = os.path.basename(template_file)
            logger.info(f"Validating template: {template_name}")
            
            soup = self.parse_html_template(template_file)
            if not soup:
                results["templates_with_issues"].append({
                    "template": template_name,
                    "error": "Failed to parse template"
                })
                results["all_valid"] = False
                continue
            
            results["templates_checked"].append(template_name)
            
            # Run all checks
            common_check = self.check_common_elements(soup, template_name)
            access_check = self.check_accessibility(soup, template_name)
            css_check = self.check_css_consistency(soup, template_name)
            color_check = self.check_color_consistency(soup, template_name)
            resp_check = self.check_responsive_design(soup, template_name)
            
            # Add check results
            results["common_elements_check"].append(common_check)
            results["accessibility_check"].append(access_check)
            results["css_consistency_check"].append(css_check)
            results["color_consistency_check"].append(color_check)
            results["responsive_design_check"].append(resp_check)
            
            # Check if this template has any issues
            has_issues = (
                common_check["missing_elements"] or
                access_check["accessibility_issues"] or
                css_check["css_issues"] or
                color_check["color_issues"] or
                resp_check["responsive_issues"]
            )
            
            if has_issues:
                results["templates_with_issues"].append({
                    "template": template_name,
                    "common_elements_missing": common_check["missing_elements"],
                    "accessibility_issues": len(access_check["accessibility_issues"]),
                    "css_issues": len(css_check["css_issues"]),
                    "color_issues": len(color_check["color_issues"]),
                    "responsive_issues": len(resp_check["responsive_issues"])
                })
                results["all_valid"] = False
        
        # Generate summary
        summary = {
            "templates_checked": len(results["templates_checked"]),
            "templates_with_issues": len(results["templates_with_issues"]),
            "all_valid": results["all_valid"]
        }
        
        if not results["all_valid"]:
            summary["issue_summary"] = {}
            
            # Gather common elements missing across templates
            missing_elements = defaultdict(int)
            for check in results["common_elements_check"]:
                for element in check["missing_elements"]:
                    missing_elements[element] += 1
            
            if missing_elements:
                summary["issue_summary"]["common_elements"] = dict(missing_elements)
            
            # Gather accessibility issues
            a11y_issues = 0
            for check in results["accessibility_check"]:
                a11y_issues += len(check["accessibility_issues"])
            
            if a11y_issues:
                summary["issue_summary"]["accessibility"] = a11y_issues
            
            # Gather CSS issues
            css_issues = 0
            for check in results["css_consistency_check"]:
                css_issues += len(check["css_issues"])
            
            if css_issues:
                summary["issue_summary"]["css"] = css_issues
            
            # Gather color issues
            color_issues = 0
            for check in results["color_consistency_check"]:
                color_issues += len(check["color_issues"])
            
            if color_issues:
                summary["issue_summary"]["color"] = color_issues
            
            # Gather responsive issues
            responsive_issues = 0
            for check in results["responsive_design_check"]:
                responsive_issues += len(check["responsive_issues"])
            
            if responsive_issues:
                summary["issue_summary"]["responsive"] = responsive_issues
        
        results["summary"] = summary
        
        logger.info(f"UX validation completed. Templates checked: {summary['templates_checked']}, " +
                   f"Templates with issues: {summary['templates_with_issues']}, " +
                   f"All valid: {summary['all_valid']}")
        
        return results
    
    def export_results(self, results, output_path=None):
        """
        Export validation results to a JSON file.
        
        Args:
            results: Validation results
            output_path: Path to output file (optional)
            
        Returns:
            str: Path to the output file
        """
        if not output_path:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "validation_reports")
            
            # Create directory if it doesn't exist
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"ux_validation_{timestamp}.json")
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"UX validation results exported to {output_path}")
        return output_path

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set templates directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    templates_dir = os.path.join(parent_dir, 'templates')
    
    # Run validation
    validator = UXValidator(templates_dir)
    results = validator.validate_templates()
    
    # Export results
    validator.export_results(results)
    
    # Print summary
    print("\nUX Validation Summary:")
    print(f"Templates checked: {results['summary']['templates_checked']}")
    print(f"Templates with issues: {results['summary']['templates_with_issues']}")
    print(f"All valid: {results['summary']['all_valid']}")
    
    if not results['summary']['all_valid'] and 'issue_summary' in results['summary']:
        print("\nIssues Summary:")
        for category, count in results['summary']['issue_summary'].items():
            print(f"- {category.title()}: {count}")