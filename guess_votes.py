#!/usr/bin/env python3
"""
Play the Guess Votes game for ballot anonymization testing.

First, generate test case

Creates:
1. A CVR file with ballots in different styles
2. A parallel spreadsheet showing voter probabilities for each candidate

When CVR is published, probabilities can be refined based on:
- Style-level vote counts for common styles (≥10 ballots)
- Aggregated vote counts for rare styles that were aggregated
- Overall election results as fallback
"""

import csv
import argparse
import os
from collections import defaultdict

# Test case configuration
# 1 ballot in style 1R1 (rare, contest A only)
# 10 ballots in style 2S2 (common, contests A and B)
# 10 ballots in style 1S3 (common, contest B only)

# Contest A: A0, A1
# Contest B: B0, B1

# Create CVR file
def create_cvr_file(election_name):
    """Create the CVR test file."""
    
    # Line 1: Version/Election name
    version = [election_name, "V1"]
    version.extend([""] * 6)  # Fill to match headerlen
    
    # Line 2: Contest names (repeated for each choice)
    contests = [""] * 8  # Header columns
    contests.extend(["A", "A"])  # Contest A appears twice (for A0, A1)
    contests.extend(["B", "B"])  # Contest B appears twice (for B0, B1)
    
    # Line 3: Choice/candidate names
    choices = [""] * 8
    choices.extend(["A0", "A1", "B0", "B1"])
    
    # Line 4: Headers
    headers = ["CvrNumber", "TabulatorNum", "BatchId", "RecordId", "ImprintedId", 
               "CountingGroup", "PrecinctPortion", "BallotType"]
    headers.extend(["A0", "A1", "B0", "B1"])
    
    # Create ballots
    ballots = []
    
    # Style 1R1: 1 ballot, contest A only
    # PrecinctPortion should start with "1R1" (first 3 chars used for style signature)
    ballots.append({
        "cvr": 1,
        "tabulator": 1,
        "batch": 1,
        "record": 1,
        "imprinted": "1-1-1",
        "counting_group": "cg",
        "precinct": "1R1",
        "ballot_type": "",
        "votes": [1, 0, "", ""]  # Voted for A0, not A1, no B contest
    })
    
    # Style 2S2: 10 ballots, contests A and B
    for i in range(10):
        # Vary votes: some vote A0, some A1, some B0, some B1
        # Let's make it interesting: 6 vote A0, 4 vote A1; 5 vote B0, 5 vote B1
        vote_a = 1 if i < 6 else 0  # First 6 vote for A0
        vote_a_alt = 1 - vote_a
        vote_b = 1 if i < 5 else 0  # First 5 vote for B0
        vote_b_alt = 1 - vote_b
        
        ballots.append({
            "cvr": i + 2,
            "tabulator": 1,
            "batch": 1,
            "record": i + 2,
            "imprinted": f"1-1-{i+2}",
            "counting_group": "cg",
            "precinct": "2S2",
            "ballot_type": "",
            "votes": [vote_a, vote_a_alt, vote_b, vote_b_alt]
        })
    
    # Style 1S3: 10 ballots, contest B only
    for i in range(10):
        # 6 vote B0, 4 vote B1
        vote_b = 1 if i < 6 else 0
        vote_b_alt = 1 - vote_b
        
        ballots.append({
            "cvr": i + 12,
            "tabulator": 1,
            "batch": 1,
            "record": i + 12,
            "imprinted": f"1-1-{i+12}",
            "counting_group": "cg",
            "precinct": "1S3",
            "ballot_type": "",
            "votes": ["", "", vote_b, vote_b_alt]  # No A contest
        })
    
    # Write CVR file
    with open("test_case_cvr.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator='\n')
        writer.writerow(version)
        writer.writerow(contests)
        writer.writerow(choices)
        writer.writerow(headers)
        
        for ballot in ballots:
            row = [
                str(ballot["cvr"]),
                str(ballot["tabulator"]),
                str(ballot["batch"]),
                str(ballot["record"]),
                ballot["imprinted"],
                ballot["counting_group"],
                ballot["precinct"],
                ballot["ballot_type"]
            ]
            row.extend([str(v) if v != "" else "" for v in ballot["votes"]])
            writer.writerow(row)
    
    return ballots

def read_cvr_file(cvr_file, headerlen=8, stylecol=6):
    """Read a CVR file and return ballots grouped by style."""
    ballots_by_style = defaultdict(list)
    
    with open(cvr_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        # Skip headers
        next(reader)  # version
        next(reader)  # contests
        next(reader)  # choices
        next(reader)  # headers
        
        for row in reader:
            if len(row) <= stylecol:
                continue
            
            style = row[stylecol].strip()
            votes = []
            for v in row[headerlen:]:
                v = v.strip()
                if v == "":
                    votes.append("")
                elif v == "0" or v == "1":
                    votes.append(int(v))
                else:
                    # Try to parse as integer (aggregated rows have vote counts)
                    try:
                        votes.append(int(v))
                    except ValueError:
                        votes.append(v)
            
            ballots_by_style[style].append({
                "style": style,
                "votes": votes
            })
    
    return ballots_by_style

def read_ballots_from_cvr(cvr_file, headerlen=8, stylecol=6):
    """Read ballots from CVR file and return in format needed for probability calculation."""
    ballots = []
    ballots_by_style = read_cvr_file(cvr_file, headerlen, stylecol)
    
    for style, style_ballots in ballots_by_style.items():
        for ballot in style_ballots:
            ballots.append({
                "precinct": style,
                "votes": ballot["votes"]
            })
    
    return ballots

def calculate_style_probabilities(ballots_by_style, min_ballots=10):
    """Calculate probabilities for each style based on CVR data.
    
    For aggregated rows, the votes are counts (sums), not individual ballot votes.
    We need to handle them differently - use the vote counts directly to calculate probabilities.
    """
    style_probs = {}
    
    for style, style_ballots in ballots_by_style.items():
        is_aggregated = style.startswith("AGGREGATED-")
        
        if is_aggregated:
            # For aggregated rows, we have vote counts (sums), not individual votes
            # Each style_ballot represents one aggregated row (with vote counts)
            if len(style_ballots) == 0:
                continue
            
            # Get the aggregated row (should be only one)
            aggregated_ballot = style_ballots[0]
            votes = aggregated_ballot["votes"]
            
            # The votes are counts (sums), so we use them directly
            # Handle both string and numeric formats
            total_a0 = 0
            total_a1 = 0
            total_b0 = 0
            total_b1 = 0
            
            if len(votes) > 0:
                val = votes[0]
                if isinstance(val, (int, float)):
                    total_a0 = int(val)
                elif isinstance(val, str) and val.strip() and val.strip().isdigit():
                    total_a0 = int(val.strip())
            
            if len(votes) > 1:
                val = votes[1]
                if isinstance(val, (int, float)):
                    total_a1 = int(val)
                elif isinstance(val, str) and val.strip() and val.strip().isdigit():
                    total_a1 = int(val.strip())
            
            if len(votes) > 2:
                val = votes[2]
                if isinstance(val, (int, float)):
                    total_b0 = int(val)
                elif isinstance(val, str) and val.strip() and val.strip().isdigit():
                    total_b0 = int(val.strip())
            
            if len(votes) > 3:
                val = votes[3]
                if isinstance(val, (int, float)):
                    total_b1 = int(val)
                elif isinstance(val, str) and val.strip() and val.strip().isdigit():
                    total_b1 = int(val.strip())
            
            # Total votes for each contest
            total_a = total_a0 + total_a1
            total_b = total_b0 + total_b1
            
            # Calculate probabilities from vote counts
            prob_a0 = total_a0 / total_a if total_a > 0 else 0.0
            prob_a1 = total_a1 / total_a if total_a > 0 else 0.0
            prob_b0 = total_b0 / total_b if total_b > 0 else 0.0
            prob_b1 = total_b1 / total_b if total_b > 0 else 0.0
            
            # Estimate ballot count from the aggregate (use max of contest totals as proxy)
            estimated_ballots = max(total_a, total_b) if (total_a > 0 or total_b > 0) else 1
            
        else:
            # Regular ballots - count individual votes
            votes_a0 = 0
            votes_a1 = 0
            votes_b0 = 0
            votes_b1 = 0
            eligible_a = 0
            eligible_b = 0
            
            for ballot in style_ballots:
                votes = ballot["votes"]
                if len(votes) >= 2:
                    if votes[0] != "" or votes[1] != "":  # Contest A on ballot
                        eligible_a += 1
                        if votes[0] == 1:
                            votes_a0 += 1
                        elif votes[1] == 1:
                            votes_a1 += 1
                    
                    if len(votes) >= 4:
                        if votes[2] != "" or votes[3] != "":  # Contest B on ballot
                            eligible_b += 1
                            if votes[2] == 1:
                                votes_b0 += 1
                            elif votes[3] == 1:
                                votes_b1 += 1
            
            # Calculate probabilities for this style
            prob_a0 = votes_a0 / eligible_a if eligible_a > 0 else 0.0
            prob_a1 = votes_a1 / eligible_a if eligible_a > 0 else 0.0
            
            prob_b0 = votes_b0 / eligible_b if eligible_b > 0 else 0.0
            prob_b1 = votes_b1 / eligible_b if eligible_b > 0 else 0.0
            
            estimated_ballots = len(style_ballots)
        
        is_common = estimated_ballots >= min_ballots
        
        style_probs[style] = {
            "prob_a0": prob_a0,
            "prob_a1": prob_a1,
            "prob_b0": prob_b0,
            "prob_b1": prob_b1,
            "is_common": is_common,
            "is_aggregated": is_aggregated,
            "ballot_count": estimated_ballots
        }
    
    return style_probs

def calculate_overall_probabilities(ballots):
    """Calculate overall election probabilities from ballots."""
    total_votes_a0 = 0
    total_votes_a1 = 0
    total_votes_b0 = 0
    total_votes_b1 = 0
    total_eligible_a = 0
    total_eligible_b = 0
    
    for ballot in ballots:
        votes = ballot["votes"]
        if votes[0] != "" or votes[1] != "":  # Contest A on ballot
            total_eligible_a += 1
            if votes[0] == 1 or votes[0] == "1":
                total_votes_a0 += 1
            elif votes[1] == 1 or votes[1] == "1":
                total_votes_a1 += 1
        
        if votes[2] != "" or votes[3] != "":  # Contest B on ballot
            total_eligible_b += 1
            if votes[2] == 1 or votes[2] == "1":
                total_votes_b0 += 1
            elif votes[3] == 1 or votes[3] == "1":
                total_votes_b1 += 1
    
    # Overall probabilities
    prob_a0 = total_votes_a0 / total_eligible_a if total_eligible_a > 0 else 0.0
    prob_a1 = total_votes_a1 / total_eligible_a if total_eligible_a > 0 else 0.0
    prob_undervote_a = 1.0 - prob_a0 - prob_a1
    
    prob_b0 = total_votes_b0 / total_eligible_b if total_eligible_b > 0 else 0.0
    prob_b1 = total_votes_b1 / total_eligible_b if total_eligible_b > 0 else 0.0
    prob_undervote_b = 1.0 - prob_b0 - prob_b1
    
    return {
        "prob_a0": prob_a0,
        "prob_a1": prob_a1,
        "prob_b0": prob_b0,
        "prob_b1": prob_b1,
        "undervote_a": prob_undervote_a,
        "undervote_b": prob_undervote_b,
        "votes_a0": total_votes_a0,
        "votes_a1": total_votes_a1,
        "votes_b0": total_votes_b0,
        "votes_b1": total_votes_b1,
        "eligible_a": total_eligible_a,
        "eligible_b": total_eligible_b
    }

def format_prob(p):
    """Format probabilities to 4 significant digits."""
    if p == 0.0:
        return "0.0000"
    if p >= 1.0:
        return "1.000"
    # Use 4 significant digits - format as 0.xxxx
    s = f"{p:.4f}"
    return s[:6] if len(s) >= 6 else s.ljust(6, "0")

def write_probability_spreadsheet(ballots, output_file, overall_probs, style_probs=None, style_mapping=None):
    """Write probability spreadsheet to file.
    
    Args:
        ballots: List of ballot dictionaries from original CVR
        output_file: Path to output CSV file
        overall_probs: Dictionary of overall probabilities
        style_probs: Optional dictionary of style-specific probabilities (from CVR)
        style_mapping: Optional mapping from original styles to anonymized styles
    """
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator='\n')
        
        # Headers
        writer.writerow(["Voter", "Style", "A0", "A1", "B0", "B1"])
        
        # One row per voter
        for i, ballot in enumerate(ballots, 1):
            voter_name = f"V{i}"
            original_style = ballot["precinct"]
            
            # If we have a style mapping (for anonymized CVR), use it to find the anonymized style
            if style_mapping and original_style in style_mapping:
                style = style_mapping[original_style]
            else:
                style = original_style
            
            votes = ballot["votes"]
            
            # Determine probabilities based on CVR data if available
            if style_probs and style in style_probs:
                # Use style-specific probabilities from CVR
                style_prob = style_probs[style]
                if votes[0] != "" or votes[1] != "":  # Contest A on ballot
                    p_a0 = format_prob(style_prob["prob_a0"])
                    p_a1 = format_prob(style_prob["prob_a1"])
                else:
                    p_a0 = ""  # Contest not on ballot
                    p_a1 = ""
                
                if votes[2] != "" or votes[3] != "":  # Contest B on ballot
                    p_b0 = format_prob(style_prob["prob_b0"])
                    p_b1 = format_prob(style_prob["prob_b1"])
                else:
                    p_b0 = ""  # Contest not on ballot
                    p_b1 = ""
            else:
                # Use overall probabilities
                if votes[0] != "" or votes[1] != "":  # Contest A on ballot
                    p_a0 = format_prob(overall_probs["prob_a0"])
                    p_a1 = format_prob(overall_probs["prob_a1"])
                else:
                    p_a0 = ""  # Contest not on ballot
                    p_a1 = ""
                
                if votes[2] != "" or votes[3] != "":  # Contest B on ballot
                    p_b0 = format_prob(overall_probs["prob_b0"])
                    p_b1 = format_prob(overall_probs["prob_b1"])
                else:
                    p_b0 = ""  # Contest not on ballot
                    p_b1 = ""
            
            writer.writerow([voter_name, style, p_a0, p_a1, p_b0, p_b1])

def create_probability_spreadsheets(ballots, original_cvr_file=None, anonymized_cvr_file=None, min_ballots=10):
    """Create probability spreadsheets: one with overall results, one refined by original CVR, one by anonymized CVR.
    
    Generates:
    - test_case_results_probabilities.csv: Using overall election results only
    - test_case_original_probabilities.csv: Using original CVR file to refine probabilities
    - test_case_anonymized_probabilities.csv: Using anonymized CVR file to refine probabilities
    """
    
    # Calculate overall election probabilities
    overall_probs = calculate_overall_probabilities(ballots)
    
    print(f"Overall election results:")
    print(f"  Contest A: A0={overall_probs['votes_a0']}/{overall_probs['eligible_a']} ({overall_probs['prob_a0']:.4f}), A1={overall_probs['votes_a1']}/{overall_probs['eligible_a']} ({overall_probs['prob_a1']:.4f}), Undervote={overall_probs['undervote_a']:.4f}")
    print(f"  Contest B: B0={overall_probs['votes_b0']}/{overall_probs['eligible_b']} ({overall_probs['prob_b0']:.4f}), B1={overall_probs['votes_b1']}/{overall_probs['eligible_b']} ({overall_probs['prob_b1']:.4f}), Undervote={overall_probs['undervote_b']:.4f}")
    
    # Write overall results spreadsheet (no CVR refinement)
    write_probability_spreadsheet(ballots, "test_case_results_probabilities.csv", overall_probs, style_probs=None)
    print(f"\nCreated test_case_results_probabilities.csv (using overall election results)")
    
    # If original CVR file is provided, read it and calculate style-level probabilities
    if original_cvr_file and os.path.exists(original_cvr_file):
        ballots_by_style = read_cvr_file(original_cvr_file)
        style_probs = calculate_style_probabilities(ballots_by_style, min_ballots)
        print(f"\nUsing original CVR file to refine probabilities:")
        print(f"  Found {len(style_probs)} styles")
        for style, probs in style_probs.items():
            status = "common" if probs["is_common"] else ("aggregated" if probs["is_aggregated"] else "rare")
            print(f"    {style}: {probs['ballot_count']} ballots ({status})")
        
        # Write original probabilities spreadsheet
        write_probability_spreadsheet(ballots, "test_case_original_probabilities.csv", overall_probs, style_probs=style_probs)
        print(f"Created test_case_original_probabilities.csv (using original CVR-refined probabilities)")
    else:
        print(f"\nNo original CVR file provided - creating test_case_original_probabilities.csv with overall results")
        write_probability_spreadsheet(ballots, "test_case_original_probabilities.csv", overall_probs, style_probs=None)
    
    # If anonymized CVR file is provided, read it and calculate style-level probabilities
    if anonymized_cvr_file and os.path.exists(anonymized_cvr_file):
        anonymized_ballots_by_style = read_cvr_file(anonymized_cvr_file)
        anonymized_style_probs = calculate_style_probabilities(anonymized_ballots_by_style, min_ballots)
        print(f"\nUsing anonymized CVR file to refine probabilities:")
        print(f"  Found {len(anonymized_style_probs)} styles")
        for style, probs in anonymized_style_probs.items():
            status = "common" if probs["is_common"] else ("aggregated" if probs["is_aggregated"] else "rare")
            print(f"    {style}: {probs['ballot_count']} ballots ({status})")
        
        # Build mapping from original styles to anonymized styles
        # For styles that were aggregated, we need to map them to the aggregated style
        # Read original CVR to see which styles exist
        original_ballots_by_style = read_cvr_file(original_cvr_file) if original_cvr_file and os.path.exists(original_cvr_file) else {}
        style_mapping = {}
        
        # Find which original styles were aggregated
        # Styles that appear in original but not in anonymized (and are rare) were aggregated
        for orig_style in original_ballots_by_style.keys():
            if orig_style not in anonymized_ballots_by_style:
                # This style was aggregated - find the aggregated style
                # Look for AGGREGATED-* styles in anonymized
                for anon_style in anonymized_style_probs.keys():
                    if anon_style.startswith("AGGREGATED-"):
                        style_mapping[orig_style] = anon_style
                        break
        
        # Also map styles that still exist (common styles)
        for orig_style in original_ballots_by_style.keys():
            if orig_style in anonymized_ballots_by_style:
                style_mapping[orig_style] = orig_style
        
        # Write anonymized probabilities spreadsheet with style mapping
        write_probability_spreadsheet(ballots, "test_case_anonymized_probabilities.csv", overall_probs, 
                                     style_probs=anonymized_style_probs, style_mapping=style_mapping)
        print(f"Created test_case_anonymized_probabilities.csv (using anonymized CVR-refined probabilities)")
    else:
        print(f"\nNo anonymized CVR file provided - creating test_case_anonymized_probabilities.csv with overall results")
        write_probability_spreadsheet(ballots, "test_case_anonymized_probabilities.csv", overall_probs, style_probs=None)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test case for ballot anonymization testing")
    parser.add_argument("original_cvr_file", nargs="?", default=None,
                        help="Path to original CVR file (default: generate test case and use it)")
    parser.add_argument("--anonymized-cvr", "-a", default=None,
                        help="Path to anonymized CVR file to compare probabilities")
    parser.add_argument("--election-name", "-n", default="Test Election 2024",
                        help="Name of the election (default: 'Test Election 2024')")
    parser.add_argument("--min-ballots", "-m", type=int, default=10,
                        help="Minimum ballots per style to be considered common (default: 10)")
    args = parser.parse_args()
    
    # If original CVR file not provided, generate test case
    if args.original_cvr_file is None:
        ballots = create_cvr_file(args.election_name)
        print(f"Created CVR file with {len(ballots)} ballots")
        original_cvr_file = "test_case_cvr.csv"
    else:
        # Read ballots from existing original CVR file
        original_cvr_file = args.original_cvr_file
        ballots = read_ballots_from_cvr(original_cvr_file)
        print(f"Read original CVR file with {len(ballots)} ballots")
    
    create_probability_spreadsheets(ballots, 
                                   original_cvr_file=original_cvr_file, 
                                   anonymized_cvr_file=args.anonymized_cvr,
                                   min_ballots=args.min_ballots)
    print("\nCreated all probability spreadsheets")

