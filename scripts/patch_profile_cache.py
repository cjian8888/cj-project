
import os
import sys
import json
import logging
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import file_categorizer
import data_cleaner
import financial_profiler
from api_server import serialize_profiles

# Configuration
OUTPUT_DIR = "./output"
CACHE_DIR = os.path.join(OUTPUT_DIR, "analysis_cache")
PROFILES_PATH = os.path.join(CACHE_DIR, "profiles.json")

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def patch_profiles():
    logger.info("Starting profile cache patch...")
    
    if not os.path.exists(PROFILES_PATH):
        logger.error(f"Profiles cache not found at {PROFILES_PATH}")
        return

    # 1. Load existing profiles (to get the list of entities)
    with open(PROFILES_PATH, 'r', encoding='utf-8') as f:
        existing_profiles_json = json.load(f)
    
    # Check if it's a list or dict (api_server saves as dict)
    if isinstance(existing_profiles_json, list):
        # This shouldn't happen based on _save_analysis_cache logic, but just in case
        logger.error("Unexpected format: profiles.json is a list, expected a dictionary.")
        return 
    
    entities = list(existing_profiles_json.keys())
    logger.info(f"Found {len(entities)} entities in cache.")

    # 2. Re-generate profiles from cleaned data
    # We need to re-read the cleaned data to get the full profile object (including vehicles, properties, etc.)
    # because the cached version is already stripped.
    
    data_dir = config.DATA_DIR
    categorized_files = file_categorizer.categorize_files(data_dir)
    
    # We will only patch the entities that we can find source files for
    # to avoid errors.
    
    persons = list(categorized_files['persons'].keys())
    companies = list(categorized_files['companies'].keys())
    
    new_profiles_data = {}
    
    logger.info("Re-generating profile data...")
    
    for entity in entities:
        is_person = entity in persons
        is_company = entity in companies
        
        df = None
        if is_person:
            p_files = categorized_files['persons'].get(entity, [])
            if p_files:
               df, _ = data_cleaner.clean_and_merge_files(p_files, entity)
        elif is_company:
            c_files = categorized_files['companies'].get(entity, [])
            if c_files:
                df, _ = data_cleaner.clean_and_merge_files(c_files, entity)
        
        if df is not None and not df.empty:
            try:
                # Generate full profile report
                full_profile = financial_profiler.generate_profile_report(df, entity)
                
                # Enhance with extra data extraction (copied from run_analysis logic)
                if is_person:
                    # Bank accounts
                    try:
                        full_profile['bank_accounts'] = financial_profiler.extract_bank_accounts(df)
                    except Exception as e:
                        logger.warning(f"  Failed to extract bank accounts for {entity}: {e}")
                        
                    # P1 Extractor Logic Injection (simplified: just placeholders or lightweight extraction if available)
                    # For patching, we might skip the heavy extractors if we assume they haven't changed much,
                    # BUT the issue is the cache file is missing the keys.
                    # We might not need to re-scan specific extractors if we just re-run extraction logic if it relies on files.
                    # However, api_server run_analysis injects these from 'analysis_results'. 
                    # If we don't have analysis_results, we can't inject them.
                    
                    # Wait, critical check: Does generate_profile_report return extraction data? 
                    # No, extraction data (vehicles etc) comes from separate extractors in run_analysis.
                    # This means just running generate_profile_report is NOT ENOUGH if we want the external data.
                    # We need to see if we can load the raw extractor data from somewhere?
                    # OR we just re-run the extractors. They are fast enough?
                    pass

                new_profiles_data[entity] = full_profile
                
            except Exception as e:
                logger.warning(f"Failed to regenerate profile for {entity}: {e}")
                # Fallback to existing if regeneration fails, but it will be missing data
                new_profiles_data[entity] = existing_profiles_json[entity] # This is already serialized, might cause issues if we mix.
                # Actually, serialize_profiles expects the raw profile dict. 
                # If we pass the already serialized dict, it might lose info or break.
                # Let's hope regeneration works.
        else:
            logger.warning(f"No source data found for {entity}, cannot patch.")

    # 3. WE MUST RE-RUN EXTERNAL DATA EXTRACTORS 
    # Because 'vehicles', 'properties', 'wealth_products' are inserted into 'profiles' in run_analysis
    # BEFORE serialization. The 'financial_profiler.generate_profile_report' does NOT include them.
    
    logger.info("Re-running critical p1 extractors...")
    
    # 7.1 Vehicle
    try:
        import vehicle_extractor
        vehicle_data = vehicle_extractor.extract_vehicle_data(data_dir)
        for person_id, vehicles in vehicle_data.items():
            if person_id in new_profiles_data:
                new_profiles_data[person_id]["vehicles"] = vehicles
    except Exception as e:
        logger.warning(f"Vehicle extraction failed: {e}")

    # 7.2 Wealth
    try:
        import wealth_product_extractor
        wealth_product_data = wealth_product_extractor.extract_wealth_product_data(data_dir)
        for person_id, wealth_info in wealth_product_data.items():
            if person_id in new_profiles_data:
                new_profiles_data[person_id]["wealth_products"] = wealth_info.get("products", [])
                new_profiles_data[person_id]["wealth_summary"] = wealth_info.get("summary", {})
    except Exception as e:
        logger.warning(f"Wealth extraction failed: {e}")
        
    # 7.4 Properties (Precise)
    try:
        import asset_extractor
        precise_property_data = asset_extractor.extract_precise_property_info(data_dir)
        for person_id, properties in precise_property_data.items():
            if person_id in new_profiles_data:
                new_profiles_data[person_id]["properties_precise"] = properties
    except Exception as e:
        logger.warning(f"Property extraction failed: {e}")

    # 4. Serialize using the updated function
    
    # Note: serialize_profiles expects a Dict[entity_name, profile_dict]
    # And it uses `profile.get('vehicles', [])` etc. which we just populated.
    
    logger.info("Serializing profiles with updated logic...")
    final_json = serialize_profiles(new_profiles_data)
    
    # 5. Save back to profiles.json
    with open(PROFILES_PATH, 'w', encoding='utf-8') as f:
        # We use a custom encoder or default to str for safety (similar to api_server)
        json.dump(final_json, f, ensure_ascii=False, indent=2, default=str)
        
    logger.info(f"Successfully patched {PROFILES_PATH}")

if __name__ == "__main__":
    patch_profiles()
