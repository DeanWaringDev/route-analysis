#!/usr/bin/env python3
"""
Reset and regenerate all enhanced GPX files using latest enhancement logic

This script will:
1. Remove all existing enhanced GPX files from Events_2026_ENH, Events_2027_ENH, Parkrun_ENH
2. Cycle through each archived route folder
3. For each folder: move GPX to temp → enhance → move back to archive
4. Regenerates all enhanced routes with latest scoring and enhancement improvements
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

def clear_enhanced_folders():
    """Remove all GPX files from enhanced folders"""
    enhanced_folders = [
        os.path.join('..', 'GPX', 'Events_2026_ENH'),
        os.path.join('..', 'GPX', 'Events_2027_ENH'),
        os.path.join('..', 'GPX', 'Parkrun_ENH')
    ]
    
    print("🗑️  Clearing existing enhanced GPX files...")
    total_removed = 0
    
    for folder in enhanced_folders:
        if os.path.exists(folder):
            gpx_files = [f for f in os.listdir(folder) if f.lower().endswith('.gpx')]
            for gpx_file in gpx_files:
                file_path = os.path.join(folder, gpx_file)
                os.remove(file_path)
                total_removed += 1
            print(f"  📁 {os.path.basename(folder)}: Removed {len(gpx_files)} files")
        else:
            print(f"  ⚠️  Folder not found: {folder}")
    
    print(f"✅ Cleared {total_removed} enhanced GPX files")
    return total_removed

def get_archive_folders():
    """Get list of all archive route folders"""
    archive_base = os.path.join('..', 'GPX', 'Archive_Routes')
    
    if not os.path.exists(archive_base):
        print(f"❌ Archive_Routes folder not found: {archive_base}")
        return []
    
    archive_folders = []
    for item in os.listdir(archive_base):
        item_path = os.path.join(archive_base, item)
        if os.path.isdir(item_path):
            # Check if folder contains GPX files
            gpx_files = [f for f in os.listdir(item_path) if f.lower().endswith('.gpx')]
            if gpx_files:
                archive_folders.append((item, item_path, len(gpx_files)))
    
    return archive_folders

def move_files_to_temp(source_folder):
    """Move all GPX files from source folder to GPX_Temp"""
    temp_folder = os.path.join('..', 'GPX', 'GPX_Temp')
    
    # Ensure temp folder exists and is empty
    if os.path.exists(temp_folder):
        # Clear existing temp files
        for f in os.listdir(temp_folder):
            if f.lower().endswith('.gpx'):
                os.remove(os.path.join(temp_folder, f))
    else:
        os.makedirs(temp_folder)
    
    # Copy GPX files to temp (don't move, copy for safety)
    moved_files = []
    for filename in os.listdir(source_folder):
        if filename.lower().endswith('.gpx'):
            src = os.path.join(source_folder, filename)
            dst = os.path.join(temp_folder, filename)
            shutil.copy2(src, dst)
            moved_files.append(filename)
    
    return moved_files

def move_files_back_to_archive(archive_folder, moved_files):
    """Files are copied, not moved, so nothing to restore"""
    pass

def run_enhancement(folder_name):
    """Run create_enhanced_gpx.py with folder_name.gpx as input"""
    input_filename = f"{folder_name}.gpx"
    
    print(f"    🔧 Running enhancement for: {input_filename}")
    
    try:
        # Set environment for UTF-8 encoding
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        
        # Run the enhancement script with input
        result = subprocess.run(
            ['python', 'create_enhanced_gpx.py'],
            input=input_filename + '\n',
            text=True,
            capture_output=True,
            cwd=os.getcwd(),
            env=env,
            encoding='utf-8'
        )
        
        if result.returncode == 0:
            print(f"    ✅ Enhancement completed successfully")
            return True
        else:
            print(f"    ❌ Enhancement failed")
            # Only show last few lines of error to avoid clutter
            if result.stderr:
                error_lines = result.stderr.strip().split('\n')
                for line in error_lines[-2:]:
                    if line.strip():
                        print(f"    {line}")
            return False
            
    except Exception as e:
        print(f"    ❌ Error running enhancement: {e}")
        return False

def main():
    print("🔄 ENHANCED GPX RESET & REGENERATION TOOL")
    print("=" * 50)
    print("This will regenerate ALL enhanced GPX files with latest logic")
    
    # Confirm with user
    response = input("\n⚠️  This will delete all existing enhanced files. Continue? (y/N): ").strip().lower()
    if response != 'y':
        print("❌ Operation cancelled")
        return
    
    # Step 1: Clear existing enhanced files
    print(f"\n📋 STEP 1: Clearing existing enhanced files...")
    cleared_count = clear_enhanced_folders()
    
    # Step 2: Get archive folders
    print(f"\n📋 STEP 2: Finding archived route folders...")
    archive_folders = get_archive_folders()
    
    if not archive_folders:
        print("❌ No archive folders found with GPX files")
        return
    
    print(f"📊 Found {len(archive_folders)} archived route folders:")
    for folder_name, folder_path, file_count in archive_folders:
        print(f"  📁 {folder_name}: {file_count} GPX files")
    
    # Step 3: Process each archive folder
    print(f"\n📋 STEP 3: Processing archived routes...")
    processed_count = 0
    failed_count = 0
    
    for folder_name, folder_path, file_count in archive_folders:
        print(f"\n🔄 Processing: {folder_name}")
        print(f"  📁 Archive folder: {folder_path}")
        print(f"  📊 GPX files: {file_count}")
        
        try:
            # Move files to temp
            print(f"  📤 Moving files to GPX_Temp...")
            moved_files = move_files_to_temp(folder_path)
            print(f"    Moved {len(moved_files)} files")
            
            # Run enhancement
            success = run_enhancement(folder_name)
            
            # Move files back
            print(f"  📥 Moving files back to archive...")
            move_files_back_to_archive(folder_path, moved_files)
            print(f"    Restored {len(moved_files)} files to archive")
            
            if success:
                processed_count += 1
                print(f"  ✅ {folder_name} completed successfully")
            else:
                failed_count += 1
                print(f"  ❌ {folder_name} failed enhancement")
                
        except Exception as e:
            failed_count += 1
            print(f"  ❌ Error processing {folder_name}: {e}")
            
            # Try to restore files if something went wrong
            try:
                moved_files = [f for f in os.listdir(os.path.join('..', 'GPX', 'GPX_Temp')) 
                              if f.lower().endswith('.gpx')]
                if moved_files:
                    move_files_back_to_archive(folder_path, moved_files)
                    print(f"    🔄 Restored {len(moved_files)} files after error")
            except:
                pass
    
    # Final summary
    print(f"\n" + "=" * 50)
    print(f"📊 REGENERATION COMPLETE")
    print(f"  Original enhanced files cleared: {cleared_count}")
    print(f"  Archive folders found: {len(archive_folders)}")
    print(f"  Successfully processed: {processed_count}")
    print(f"  Failed: {failed_count}")
    
    if failed_count == 0:
        print(f"\n🎉 ALL ENHANCED GPX FILES REGENERATED SUCCESSFULLY!")
        print(f"   All files now use the latest enhancement logic and scoring")
    else:
        print(f"\n⚠️  Some files failed to regenerate. Check the errors above.")
        
    print(f"\nℹ️  Enhanced files are now located in:")
    print(f"   📁 GPX/Events_2026_ENH/")
    print(f"   📁 GPX/Events_2027_ENH/") 
    print(f"   📁 GPX/Parkrun_ENH/")

if __name__ == "__main__":
    main()