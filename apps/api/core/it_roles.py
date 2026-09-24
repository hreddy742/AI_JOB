"""Taxonomy dictionary for comprehensive IT job scraping in the US."""

from __future__ import annotations

# Matrix of top 50 US Tech Hubs and Major Cities
US_CITIES: tuple[str, ...] = (
    "New York, NY", "San Francisco, CA", "Seattle, WA", "Austin, TX",
    "Boston, MA", "Chicago, IL", "Los Angeles, CA", "Washington, DC",
    "Atlanta, GA", "Dallas, TX", "Denver, CO", "San Diego, CA",
    "San Jose, CA", "Philadelphia, PA", "Raleigh, NC", "Charlotte, NC",
    "Portland, OR", "Phoenix, AZ", "Miami, FL", "Houston, TX",
    "Minneapolis, MN", "Salt Lake City, UT", "Detroit, MI", "Baltimore, MD",
    "Columbus, OH", "Durham, NC", "Pittsburgh, PA", "St. Louis, MO",
    "Orlando, FL", "Indianapolis, IN", "Nashville, TN", "Tampa, FL",
    "Cincinnati, OH", "Kansas City, MO", "Milwaukee, WI", "Cleveland, OH",
    "Sacramento, CA", "San Antonio, TX", "Las Vegas, NV", "Richmond, VA",
    "Hartford, CT", "Providence, RI", "Jacksonville, FL", "Memphis, TN",
    "Louisville, KY", "New Orleans, LA", "Oklahoma City, OK", "Des Moines, IA",
    "Omaha, NE", "Boise, ID"
)

# Taxonomy grouped by domain for intelligent searching
IT_ROLE_TAXONOMY: dict[str, dict[str, list[str]]] = {
    "software_engineering": {
        "backend": [
            "Backend Engineer", "Backend Developer", "Server Side Engineer",
            "Python Developer", "Java Developer", "Golang Engineer",
            "Node.js Developer", "C++ Engineer", "API Developer"
        ],
        "frontend": [
            "Frontend Engineer", "Frontend Developer", "UI Engineer",
            "React Developer", "Vue Developer", "Angular Developer",
            "Web Developer", "JavaScript Engineer"
        ],
        "full_stack": [
            "Full Stack Engineer", "Full Stack Developer", "Software Engineer",
            "SDE", "SDE II", "Senior Software Engineer", "Software Developer",
            "Application Developer", "Systems Programmer"
        ],
        "mobile": [
            "iOS Developer", "Android Developer", "Mobile Engineer",
            "Flutter Developer", "React Native Developer", "Swift Developer"
        ]
    },
    "data_and_ml": {
        "data_engineering": [
            "Data Engineer", "Big Data Engineer", "ETL Developer",
            "Spark Engineer", "Data Warehouse Engineer", "Data Pipeline Engineer"
        ],
        "data_science": [
            "Data Scientist", "Machine Learning Scientist", "Decision Scientist",
            "Applied Scientist"
        ],
        "machine_learning": [
            "Machine Learning Engineer", "ML Engineer", "MLE",
            "AI Engineer", "Computer Vision Engineer", "NLP Engineer",
            "LLM Engineer", "Generative AI Engineer"
        ],
        "analytics": [
            "Data Analyst", "Business Intelligence Analyst", "BI Developer",
            "Analytics Engineer", "Product Analyst"
        ]
    },
    "infrastructure_and_security": {
        "devops_cloud": [
            "DevOps Engineer", "Site Reliability Engineer", "SRE",
            "Cloud Engineer", "Platform Engineer", "AWS Engineer",
            "Azure Architect", "Kubernetes Administrator"
        ],
        "security": [
            "Security Engineer", "Cybersecurity Analyst", "Information Security",
            "Penetration Tester", "AppSec Engineer", "Network Security Engineer"
        ],
        "system_admin": [
            "System Administrator", "Network Engineer", "IT Support Specialist",
            "IT Manager", "Systems Administrator"
        ]
    },
    "product_and_design": {
        "product_management": [
            "Product Manager", "Technical Product Manager", "PM",
            "Product Owner"
        ],
        "design": [
            "Product Designer", "UI/UX Designer", "UX Researcher",
            "Interaction Designer"
        ]
    }
}

def get_all_role_variants() -> list[str]:
    """Flatten taxonomy into a single list of all search variants."""
    variants = []
    for domain, categories in IT_ROLE_TAXONOMY.items():
        for category, roles in categories.items():
            variants.extend(roles)
    return list(set(variants))
