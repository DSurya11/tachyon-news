"""
pipeline/scraper/sector_map.py
──────────────────────────────
Static mapping from Finviz industry labels to GICS sectors.

Source: Finviz industry dropdown combined with GICS classification.
~120 entries covering the majority of stocks listed on Finviz.

Usage:
    from pipeline.scraper.sector_map import finviz_to_gics

    sector = finviz_to_gics.get("Semiconductors", "Unknown")
    # → "Technology"
"""
from __future__ import annotations

# Key:   Finviz industry label (as it appears in data-boxover-industry)
# Value: GICS sector name
FINVIZ_TO_GICS: dict[str, str] = {
    # ── Technology ──────────────────────────────────────────────────────
    "Semiconductors": "Technology",
    "Semiconductor Equipment & Materials": "Technology",
    "Software - Infrastructure": "Technology",
    "Software - Application": "Technology",
    "Computer Hardware": "Technology",
    "Electronic Components": "Technology",
    "Electronics & Computer Distribution": "Technology",
    "Scientific & Technical Instruments": "Technology",
    "Information Technology Services": "Technology",
    "Technology Distributors": "Technology",
    "Consumer Electronics": "Technology",
    "Solar": "Technology",

    # ── Communication Services ───────────────────────────────────────────
    "Internet Content & Information": "Communication Services",
    "Entertainment": "Communication Services",
    "Telecom Services": "Communication Services",
    "Broadcasting": "Communication Services",
    "Electronic Gaming & Multimedia": "Communication Services",
    "Publishing": "Communication Services",
    "Advertising Agencies": "Communication Services",
    "Pay TV": "Communication Services",

    # ── Financials ───────────────────────────────────────────────────────
    "Banks - Diversified": "Financials",
    "Banks - Regional": "Financials",
    "Asset Management": "Financials",
    "Capital Markets": "Financials",
    "Credit Services": "Financials",
    "Insurance - Life": "Financials",
    "Insurance - Property & Casualty": "Financials",
    "Insurance - Diversified": "Financials",
    "Insurance - Specialty": "Financials",
    "Insurance Brokers": "Financials",
    "Financial Data & Stock Exchanges": "Financials",
    "Mortgage Finance": "Financials",
    "Insurance - Reinsurance": "Financials",
    "Shell Companies": "Financials",

    # ── Health Care ─────────────────────────────────────────────────────
    "Drug Manufacturers - General": "Health Care",
    "Drug Manufacturers - Specialty & Generic": "Health Care",
    "Biotechnology": "Health Care",
    "Healthcare Plans": "Health Care",
    "Medical Devices": "Health Care",
    "Medical Instruments & Supplies": "Health Care",
    "Diagnostics & Research": "Health Care",
    "Health Information Services": "Health Care",
    "Medical Care Facilities": "Health Care",
    "Medical Distribution": "Health Care",
    "Pharmaceutical Retailers": "Health Care",

    # ── Consumer Discretionary ──────────────────────────────────────────
    "Auto Manufacturers": "Consumer Discretionary",
    "Auto Parts": "Consumer Discretionary",
    "Auto & Truck Dealerships": "Consumer Discretionary",
    "Restaurants": "Consumer Discretionary",
    "Internet Retail": "Consumer Discretionary",
    "Specialty Retail": "Consumer Discretionary",
    "Department Stores": "Consumer Discretionary",
    "Home Improvement Retail": "Consumer Discretionary",
    "Apparel Retail": "Consumer Discretionary",
    "Apparel Manufacturing": "Consumer Discretionary",
    "Footwear & Accessories": "Consumer Discretionary",
    "Home Furnishings & Fixtures": "Consumer Discretionary",
    "Leisure": "Consumer Discretionary",
    "Gambling": "Consumer Discretionary",
    "Lodging": "Consumer Discretionary",
    "Resorts & Casinos": "Consumer Discretionary",
    "Travel Services": "Consumer Discretionary",
    "Personal Services": "Consumer Discretionary",
    "Recreational Vehicles": "Consumer Discretionary",

    # ── Consumer Staples ────────────────────────────────────────────────
    "Beverages - Non-Alcoholic": "Consumer Staples",
    "Beverages - Brewers": "Consumer Staples",
    "Beverages - Wineries & Distilleries": "Consumer Staples",
    "Grocery Stores": "Consumer Staples",
    "Discount Stores": "Consumer Staples",
    "Packaged Foods": "Consumer Staples",
    "Confectioners": "Consumer Staples",
    "Farm Products": "Consumer Staples",
    "Household & Personal Products": "Consumer Staples",
    "Tobacco": "Consumer Staples",

    # ── Energy ──────────────────────────────────────────────────────────
    "Oil & Gas E&P": "Energy",
    "Oil & Gas Integrated": "Energy",
    "Oil & Gas Refining & Marketing": "Energy",
    "Oil & Gas Midstream": "Energy",
    "Oil & Gas Drilling": "Energy",
    "Oil & Gas Equipment & Services": "Energy",
    "Uranium": "Energy",
    "Thermal Coal": "Energy",
    "Coking Coal": "Energy",

    # ── Utilities ───────────────────────────────────────────────────────
    "Utilities - Regulated Electric": "Utilities",
    "Utilities - Regulated Gas": "Utilities",
    "Utilities - Regulated Water": "Utilities",
    "Utilities - Independent Power Producers": "Utilities",
    "Utilities - Renewable": "Utilities",
    "Utilities - Diversified": "Utilities",

    # ── Industrials ─────────────────────────────────────────────────────
    "Aerospace & Defense": "Industrials",
    "Engineering & Construction": "Industrials",
    "Integrated Freight & Logistics": "Industrials",
    "Airlines": "Industrials",
    "Trucking": "Industrials",
    "Marine Shipping": "Industrials",
    "Railroads": "Industrials",
    "Rental & Leasing Services": "Industrials",
    "Specialty Industrial Machinery": "Industrials",
    "General Industrial Equipment": "Industrials",
    "Electrical Equipment & Parts": "Industrials",
    "Metal Fabrication": "Industrials",
    "Farm & Heavy Construction Machinery": "Industrials",
    "Pollution & Treatment Controls": "Industrials",
    "Tools & Accessories": "Industrials",
    "Security & Protection Services": "Industrials",
    "Staffing & Employment Services": "Industrials",
    "Business Equipment & Supplies": "Industrials",
    "Conglomerates": "Industrials",
    "Waste Management": "Industrials",

    # ── Materials ───────────────────────────────────────────────────────
    "Steel": "Materials",
    "Aluminum": "Materials",
    "Copper": "Materials",
    "Gold": "Materials",
    "Silver": "Materials",
    "Other Precious Metals & Mining": "Materials",
    "Specialty Chemicals": "Materials",
    "Commodity Chemicals": "Materials",
    "Agricultural Inputs": "Materials",
    "Building Materials": "Materials",
    "Lumber & Wood Production": "Materials",
    "Paper & Paper Products": "Materials",
    "Packaging & Containers": "Materials",

    # ── Real Estate ─────────────────────────────────────────────────────
    "REIT - Diversified": "Real Estate",
    "REIT - Industrial": "Real Estate",
    "REIT - Office": "Real Estate",
    "REIT - Retail": "Real Estate",
    "REIT - Residential": "Real Estate",
    "REIT - Healthcare Facilities": "Real Estate",
    "REIT - Hotel & Motel": "Real Estate",
    "REIT - Mortgage": "Real Estate",
    "REIT - Specialty": "Real Estate",
    "Real Estate Services": "Real Estate",
    "Real Estate - Diversified": "Real Estate",
    "Real Estate Development": "Real Estate",

    # ── ETF / Other ─────────────────────────────────────────────────────
    "Exchange Traded Fund": "ETF",
    "Closed-End Fund - Debt": "ETF",
    "Closed-End Fund - Equity": "ETF",
    "Closed-End Fund - Foreign": "ETF",
    "Exchange Traded Fund Income": "ETF",
    "Shell Companies": "Other",
    "Specialty Finance": "Financials",
    "Other": "Other",
}

# Convenience alias (matches naming used in the plan)
finviz_to_gics = FINVIZ_TO_GICS


def get_sector(finviz_industry: str | None) -> str:
    """
    Map a Finviz industry string to a GICS sector.
    Returns 'Unknown' if the industry is None or not in the map.
    """
    if not finviz_industry:
        return "Unknown"
    return FINVIZ_TO_GICS.get(finviz_industry, "Unknown")
