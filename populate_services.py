"""
Populate Services for GlassRain

This script populates the database with initial service categories, services, and tiers.
"""

import os
import json
import logging
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('populate_services')

def get_db_connection():
    """Get a connection to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL', ''))
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return None

def populate_service_categories():
    """Populate service categories table with initial data"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if categories already exist
        cursor.execute("SELECT COUNT(*) as count FROM service_categories")
        result = cursor.fetchone()
        
        if result and result['count'] > 0:
            logger.info("Service categories already populated")
            cursor.close()
            conn.close()
            return True
        
        # Define service categories
        categories = [
            {
                "name": "Lawn Care & Landscaping",
                "description": "Professional lawn maintenance and landscaping services",
                "icon": "grass"
            },
            {
                "name": "Home Cleaning",
                "description": "Interior and exterior cleaning services",
                "icon": "spray"
            },
            {
                "name": "HVAC",
                "description": "Heating, ventilation, and air conditioning services",
                "icon": "thermometer"
            },
            {
                "name": "Plumbing",
                "description": "Plumbing installation, repair, and maintenance",
                "icon": "droplet"
            },
            {
                "name": "Electrical",
                "description": "Electrical repairs, installation, and upgrades",
                "icon": "zap"
            },
            {
                "name": "Roofing",
                "description": "Roof repair, replacement, and maintenance",
                "icon": "home"
            },
            {
                "name": "Windows & Doors",
                "description": "Window and door installation and repair",
                "icon": "square"
            },
            {
                "name": "Painting",
                "description": "Interior and exterior painting services",
                "icon": "palette"
            },
            {
                "name": "Flooring",
                "description": "Flooring installation, refinishing, and repair",
                "icon": "grid"
            },
            {
                "name": "Pest Control",
                "description": "Prevention and removal of pests",
                "icon": "bug"
            }
        ]
        
        # Insert categories
        category_ids = {}
        for category in categories:
            cursor.execute("""
                INSERT INTO service_categories (name, description, icon)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (
                category["name"],
                category["description"],
                category["icon"]
            ))
            
            category_id = cursor.fetchone()['id']
            category_ids[category["name"]] = category_id
        
        logger.info(f"Populated {len(categories)} service categories")
        
        # Define services for each category with tiers
        services_data = {
            "Lawn Care & Landscaping": [
                {
                    "name": "One-Time Lawn Cut",
                    "description": "Professional one-time lawn mowing service",
                    "image_url": "lawn_cut.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$45-$65",
                            "description": "Basic lawn mowing and edging",
                            "includes": ["Mowing", "Edging", "Blowing clippings"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$75-$95",
                            "description": "Enhanced lawn service with trimming",
                            "includes": ["Mowing", "Edging", "Trimming", "Blowing clippings", "Sidewalk edging"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$110-$150",
                            "description": "Complete lawn care package",
                            "includes": ["Mowing", "Edging", "Trimming", "Blowing clippings", "Sidewalk edging", "Fertilization", "Weed removal"]
                        }
                    ]
                },
                {
                    "name": "Seasonal Maintenance",
                    "description": "Regular lawn maintenance throughout the season",
                    "image_url": "seasonal_lawn.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$150-$200/month",
                            "description": "Bi-weekly basic maintenance",
                            "includes": ["Bi-weekly mowing", "Monthly edging", "Blowing clippings"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$250-$350/month",
                            "description": "Weekly enhanced maintenance",
                            "includes": ["Weekly mowing", "Bi-weekly edging", "Trimming", "Blowing clippings", "Monthly fertilization"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$400-$600/month",
                            "description": "Complete lawn management",
                            "includes": ["Weekly mowing", "Weekly edging", "Trimming", "Blowing clippings", "Fertilization", "Weed control", "Seasonal planting", "Irrigation check"]
                        }
                    ]
                },
                {
                    "name": "Landscape Design",
                    "description": "Professional landscape design and installation",
                    "image_url": "landscape_design.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$500-$1,500",
                            "description": "Basic landscape design",
                            "includes": ["Initial consultation", "2D design plan", "Plant selection guide"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$2,000-$5,000",
                            "description": "Enhanced landscape design with modeling",
                            "includes": ["On-site consultation", "3D design rendering", "Plant selection", "Installation guidelines", "2 revision rounds"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$5,000-$15,000+",
                            "description": "Complete landscape transformation",
                            "includes": ["Multiple consultations", "3D design rendering", "Custom plant selection", "Full installation service", "3 revision rounds", "1-year maintenance plan"]
                        }
                    ]
                }
            ],
            "Home Cleaning": [
                {
                    "name": "Regular Cleaning",
                    "description": "Thorough home cleaning service",
                    "image_url": "home_clean.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$100-$180",
                            "description": "Basic cleaning of main living areas",
                            "includes": ["Dusting", "Vacuuming", "Mopping", "Bathroom cleaning", "Kitchen cleaning"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$180-$280",
                            "description": "Deep cleaning of entire home",
                            "includes": ["Standard cleaning", "Inside cabinet cleaning", "Baseboards", "Window sills", "Light fixtures", "Door cleaning"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$280-$400+",
                            "description": "White-glove cleaning service",
                            "includes": ["Premium cleaning", "Inside refrigerator", "Inside oven", "Window cleaning", "Custom requests", "Eco-friendly products", "Laundry service"]
                        }
                    ]
                },
                {
                    "name": "Deep Cleaning",
                    "description": "Intensive deep cleaning for entire home",
                    "image_url": "deep_clean.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$200-$350",
                            "description": "Thorough deep cleaning",
                            "includes": ["Regular cleaning tasks", "Baseboards", "Door frames", "Light fixtures", "Behind appliances"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$350-$500",
                            "description": "Enhanced deep cleaning",
                            "includes": ["Standard deep cleaning", "Inside cabinets", "Inside appliances", "Window cleaning", "Upholstery vacuuming"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$500-$700+",
                            "description": "Complete restoration cleaning",
                            "includes": ["Premium deep cleaning", "Carpet deep cleaning", "Wall washing", "Ceiling fans", "Chandeliers", "Custom requests", "2-person crew minimum"]
                        }
                    ]
                }
            ],
            "HVAC": [
                {
                    "name": "HVAC Maintenance",
                    "description": "Regular maintenance for heating and cooling systems",
                    "image_url": "hvac_maintenance.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$80-$150",
                            "description": "Basic HVAC tune-up",
                            "includes": ["Filter check", "Coil inspection", "Basic system test", "Thermostat check"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$150-$250",
                            "description": "Complete HVAC service",
                            "includes": ["Standard tune-up", "Coil cleaning", "Refrigerant check", "Electrical inspection", "Ductwork inspection"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$250-$400",
                            "description": "Comprehensive HVAC service",
                            "includes": ["Premium service", "Refrigerant top-off", "Duct sanitizing", "Performance testing", "Air quality testing", "Annual maintenance plan"]
                        }
                    ]
                },
                {
                    "name": "HVAC Installation",
                    "description": "Professional installation of new HVAC systems",
                    "image_url": "hvac_install.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$3,000-$5,000",
                            "description": "Basic system installation",
                            "includes": ["Standard efficiency unit", "Basic thermostat", "Removal of old unit", "Standard warranty"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$5,000-$8,000",
                            "description": "High-efficiency system installation",
                            "includes": ["High-efficiency unit", "Smart thermostat", "Removal of old unit", "Ductwork inspection", "Extended warranty"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$8,000-$15,000+",
                            "description": "Top-of-line system installation",
                            "includes": ["Highest efficiency unit", "Smart zoning system", "Complete ductwork inspection/replacement", "Air purification system", "Extended warranty", "Annual maintenance plan"]
                        }
                    ]
                }
            ],
            "Windows & Doors": [
                {
                    "name": "Window Installation",
                    "description": "Professional window replacement and installation",
                    "image_url": "window_install.jpg",
                    "tiers": [
                        {
                            "tier_name": "Standard",
                            "price_range": "$200-$500 per window",
                            "description": "Basic energy-efficient windows",
                            "includes": ["Standard vinyl windows", "Double pane glass", "Basic installation", "Removal of old windows"]
                        },
                        {
                            "tier_name": "Premium",
                            "price_range": "$500-$800 per window",
                            "description": "Enhanced windows with better insulation",
                            "includes": ["Premium vinyl or wood windows", "Triple pane glass", "Enhanced installation", "Custom sizing", "Improved energy efficiency"]
                        },
                        {
                            "tier_name": "Luxury",
                            "price_range": "$800-$1,500+ per window",
                            "description": "Custom high-end windows",
                            "includes": ["Premium wood or fiberglass windows", "Triple pane glass", "Custom designs", "Smart tinting options", "Maximum energy efficiency", "Upgraded hardware"]
                        }
                    ]
                }
            ]
        }
        
        # Insert services and tiers
        for category_name, services in services_data.items():
            category_id = category_ids[category_name]
            
            for service in services:
                # Insert service
                cursor.execute("""
                    INSERT INTO services (category_id, name, description, image_url)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (
                    category_id,
                    service["name"],
                    service["description"],
                    service["image_url"]
                ))
                
                service_id = cursor.fetchone()['id']
                
                # Insert tiers for this service
                for tier in service["tiers"]:
                    # Set appropriate multiplier based on tier level
                    tier_multiplier = 1.0  # Default multiplier
                    if tier["tier_name"].lower() == "standard":
                        tier_multiplier = 1.0
                    elif tier["tier_name"].lower() == "premium":
                        tier_multiplier = 1.5
                    elif tier["tier_name"].lower() == "luxury":
                        tier_multiplier = 2.0
                    
                    cursor.execute("""
                        INSERT INTO service_tiers (service_id, name, description, multiplier, features)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        service_id,
                        tier["tier_name"],
                        tier["description"],
                        tier_multiplier,
                        json.dumps({"price_range": tier["price_range"], "includes": tier["includes"]})
                    ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("Successfully populated services and tiers")
        return True
        
    except Exception as e:
        logger.error(f"Error populating service categories: {str(e)}")
        return False

def populate_contractors():
    """Populate contractors table with initial data"""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if contractors already exist
        cursor.execute("SELECT COUNT(*) as count FROM contractors")
        result = cursor.fetchone()
        
        if result and result['count'] > 0:
            logger.info("Contractors already populated")
            cursor.close()
            conn.close()
            return True
        
        # Define contractors by city and service
        contractors = [
            # New York
            {
                "name": "Michael Johnson",
                "company_name": "Johnson Lawn Care",
                "description": "Professional lawn care with 15 years of experience",
                "logo_url": "johnson_lawn.jpg",
                "email": "info@johnsonlawn.com",
                "phone": "212-555-1234",
                "city": "New York",
                "state": "NY",
                "rating": 4.8,
                "services": ["Lawn Care & Landscaping"]
            },
            {
                "name": "Sarah Williams",
                "company_name": "Metro Cleaning Services",
                "description": "Top-rated home cleaning service in NYC",
                "logo_url": "metro_cleaning.jpg",
                "email": "info@metrocleaning.com",
                "phone": "212-555-2345",
                "city": "New York",
                "state": "NY",
                "rating": 4.7,
                "services": ["Home Cleaning"]
            },
            {
                "name": "David Chen",
                "company_name": "Chen HVAC Solutions",
                "description": "Expert HVAC installations and repairs",
                "logo_url": "chen_hvac.jpg",
                "email": "info@chenhvac.com",
                "phone": "212-555-3456",
                "city": "New York",
                "state": "NY",
                "rating": 4.9,
                "services": ["HVAC"]
            },
            
            # Los Angeles
            {
                "name": "Maria Rodriguez",
                "company_name": "Sunshine Landscaping",
                "description": "Beautiful landscape design for Southern California",
                "logo_url": "sunshine_landscape.jpg",
                "email": "info@sunshinelandscape.com",
                "phone": "323-555-1234",
                "city": "Los Angeles",
                "state": "CA",
                "rating": 4.6,
                "services": ["Lawn Care & Landscaping"]
            },
            {
                "name": "James Wilson",
                "company_name": "Wilson Plumbing",
                "description": "Licensed and insured plumbers serving LA County",
                "logo_url": "wilson_plumbing.jpg",
                "email": "info@wilsonplumbing.com",
                "phone": "323-555-2345",
                "city": "Los Angeles",
                "state": "CA",
                "rating": 4.5,
                "services": ["Plumbing"]
            },
            {
                "name": "Anna Kim",
                "company_name": "Pure Clean LA",
                "description": "Eco-friendly home cleaning service",
                "logo_url": "pure_clean.jpg",
                "email": "info@purecleanla.com",
                "phone": "323-555-3456",
                "city": "Los Angeles",
                "state": "CA",
                "rating": 4.8,
                "services": ["Home Cleaning"]
            },
            
            # Chicago
            {
                "name": "Robert Martinez",
                "company_name": "Windy City HVAC",
                "description": "Chicago's trusted HVAC service since 1998",
                "logo_url": "windycity_hvac.jpg",
                "email": "info@windycityhvac.com",
                "phone": "312-555-1234",
                "city": "Chicago",
                "state": "IL",
                "rating": 4.7,
                "services": ["HVAC"]
            },
            {
                "name": "Jennifer Smith",
                "company_name": "Smith Electric",
                "description": "Residential and commercial electrical services",
                "logo_url": "smith_electric.jpg",
                "email": "info@smithelectric.com",
                "phone": "312-555-2345",
                "city": "Chicago",
                "state": "IL",
                "rating": 4.9,
                "services": ["Electrical"]
            },
            {
                "name": "William Brown",
                "company_name": "Brown Roofing",
                "description": "Quality roofing solutions for Chicago weather",
                "logo_url": "brown_roofing.jpg",
                "email": "info@brownroofing.com",
                "phone": "312-555-3456",
                "city": "Chicago",
                "state": "IL",
                "rating": 4.6,
                "services": ["Roofing"]
            },
            
            # Houston
            {
                "name": "Carlos Gonzalez",
                "company_name": "Texas Landscape Pros",
                "description": "Complete landscape services for Houston homes",
                "logo_url": "texas_landscape.jpg",
                "email": "info@texaslandscapepros.com",
                "phone": "713-555-1234",
                "city": "Houston",
                "state": "TX",
                "rating": 4.5,
                "services": ["Lawn Care & Landscaping"]
            },
            {
                "name": "Elizabeth Taylor",
                "company_name": "Taylor Windows & Doors",
                "description": "Energy-efficient windows and doors installation",
                "logo_url": "taylor_windows.jpg",
                "email": "info@taylorwindows.com",
                "phone": "713-555-2345",
                "city": "Houston",
                "state": "TX",
                "rating": 4.8,
                "services": ["Windows & Doors"]
            },
            {
                "name": "Thomas Johnson",
                "company_name": "Johnson Painting",
                "description": "Professional interior and exterior painting",
                "logo_url": "johnson_painting.jpg",
                "email": "info@johnsonpainting.com",
                "phone": "713-555-3456",
                "city": "Houston",
                "state": "TX",
                "rating": 4.7,
                "services": ["Painting"]
            }
        ]
        
        # Get service categories for mapping
        cursor.execute("SELECT id, name FROM service_categories")
        categories = {row['name']: row['id'] for row in cursor.fetchall()}
        
        # Insert contractors
        for contractor in contractors:
            cursor.execute("""
                INSERT INTO contractors (
                    name, company_name, description, logo_url, 
                    email, phone, city, state, rating
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                contractor["name"],
                contractor["company_name"],
                contractor["description"],
                contractor["logo_url"],
                contractor["email"],
                contractor["phone"],
                contractor["city"],
                contractor["state"],
                contractor["rating"]
            ))
            
            contractor_id = cursor.fetchone()['id']
            
            # Associate contractor with services
            for service_category_name in contractor["services"]:
                category_id = categories.get(service_category_name)
                
                if category_id:
                    # Get services in this category
                    cursor.execute("""
                        SELECT service_id FROM services WHERE category_id = %s
                    """, (category_id,))
                    
                    services = cursor.fetchall()
                    
                    for service in services:
                        service_id = service['service_id']
                        
                        # Get tiers for this service
                        cursor.execute("""
                            SELECT tier_id FROM service_tiers WHERE service_id = %s
                        """, (service_id,))
                        
                        tiers = cursor.fetchall()
                        
                        # Associate contractor with each service and tier
                        for tier in tiers:
                            tier_id = tier['tier_id']
                            
                            cursor.execute("""
                                INSERT INTO contractor_services (contractor_id, service_id, tier_id)
                                VALUES (%s, %s, %s)
                                ON CONFLICT DO NOTHING
                            """, (contractor_id, service_id, tier_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Successfully populated {len(contractors)} contractors")
        return True
        
    except Exception as e:
        logger.error(f"Error populating contractors: {str(e)}")
        return False

def main():
    """Main function to populate all service-related data"""
    logger.info("Starting to populate service data...")
    
    # Populate service categories, services, and tiers
    if not populate_service_categories():
        logger.error("Failed to populate service categories")
        return False
        
    # Populate contractors
    if not populate_contractors():
        logger.error("Failed to populate contractors")
        return False
        
    logger.info("Successfully populated all service data")
    return True

if __name__ == "__main__":
    main()