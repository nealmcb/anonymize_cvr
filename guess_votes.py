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
                    votes.append(v)
            
            ballots_by_style[style].append({
                "style": style,
                "votes": votes
            })
    
    return ballots_by_style

def calculate_style_probabilities(ballots_by_style, min_ballots=10):
    """Calculate probabilities for each style based on CVR data."""
    style_probs = {}
    
    for style, style_ballots in ballots_by_style.items():
        # Count votes for this style
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
        
        is_common = len(style_ballots) >= min_ballots
        is_aggregated = style.startswith("AGGREGATED-")
        
        style_probs[style] = {
            "prob_a0": prob_a0,
            "prob_a1": prob_a1,
            "prob_b0": prob_b0,
            "prob_b1": prob_b1,
            "eligible_a": eligible_a,
            "eligible_b": eligible_b,
            "is_common": is_common,
            "is_aggregated": is_aggregated,
            "ballot_count": len(style_ballots)
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

def write_probability_spreadsheet(ballots, output_file, overall_probs, style_probs=None):
    """Write probability spreadsheet to file.
    
    Args:
        ballots: List of ballot dictionaries
        output_file: Path to output CSV file
        overall_probs: Dictionary of overall probabilities
        style_probs: Optional dictionary of style-specific probabilities (from CVR)
    """
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator='\n')
        
        # Headers
        writer.writerow(["Voter", "Style", "A0", "A1", "B0", "B1"])
        
        # One row per voter
        for i, ballot in enumerate(ballots, 1):
            voter_name = f"V{i}"
            style = ballot["precinct"]
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

def create_probability_spreadsheets(ballots, cvr_file=None, min_ballots=10):
    """Create both probability spreadsheets: one with overall results, one refined by CVR.
    
    Generates:
    - test_case_results_probabilities.csv: Using overall election results only
    - test_case_refined_probabilities.csv: Using CVR file to refine probabilities
    """
    
    # Calculate overall election probabilities
    overall_probs = calculate_overall_probabilities(ballots)
    
    print(f"Overall election results:")
    print(f"  Contest A: A0={overall_probs['votes_a0']}/{overall_probs['eligible_a']} ({overall_probs['prob_a0']:.4f}), A1={overall_probs['votes_a1']}/{overall_probs['eligible_a']} ({overall_probs['prob_a1']:.4f}), Undervote={overall_probs['undervote_a']:.4f}")
    print(f"  Contest B: B0={overall_probs['votes_b0']}/{overall_probs['eligible_b']} ({overall_probs['prob_b0']:.4f}), B1={overall_probs['votes_b1']}/{overall_probs['eligible_b']} ({overall_probs['prob_b1']:.4f}), Undervote={overall_probs['undervote_b']:.4f}")
    
    # Write overall results spreadsheet (no CVR refinement)
    write_probability_spreadsheet(ballots, "test_case_results_probabilities.csv", overall_probs, style_probs=None)
    print(f"\nCreated test_case_results_probabilities.csv (using overall election results)")
    
    # If CVR file is provided, read it and calculate style-level probabilities
    style_probs = {}
    if cvr_file and os.path.exists(cvr_file):
        ballots_by_style = read_cvr_file(cvr_file)
        style_probs = calculate_style_probabilities(ballots_by_style, min_ballots)
        print(f"\nUsing CVR file to refine probabilities:")
        print(f"  Found {len(style_probs)} styles")
        for style, probs in style_probs.items():
            status = "common" if probs["is_common"] else ("aggregated" if probs["is_aggregated"] else "rare")
            print(f"    {style}: {probs['ballot_count']} ballots ({status})")
        
        # Write refined probabilities spreadsheet (with CVR refinement)
        write_probability_spreadsheet(ballots, "test_case_refined_probabilities.csv", overall_probs, style_probs=style_probs)
        print(f"Created test_case_refined_probabilities.csv (using CVR-refined probabilities)")
    else:
        print(f"\nNo CVR file provided - creating test_case_refined_probabilities.csv with overall results")
        # Still create the refined file, but it will have the same data as results
        write_probability_spreadsheet(ballots, "test_case_refined_probabilities.csv", overall_probs, style_probs=None)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test case for ballot anonymization testing")
    parser.add_argument("--election-name", "-n", default="Test Election 2024",
                        help="Name of the election (default: 'Test Election 2024')")
    parser.add_argument("--cvr-file", "-c", default=None,
                        help="Path to published CVR file to refine probabilities (default: use overall results)")
    parser.add_argument("--min-ballots", "-m", type=int, default=10,
                        help="Minimum ballots per style to be considered common (default: 10)")
    args = parser.parse_args()
    
    ballots = create_cvr_file(args.election_name)
    print(f"Created CVR file with {len(ballots)} ballots")
    
    # Use the generated CVR file if no file specified, otherwise use the specified file
    cvr_file = args.cvr_file if args.cvr_file else "test_case_cvr.csv"
    create_probability_spreadsheets(ballots, cvr_file=cvr_file, min_ballots=args.min_ballots)
    print("\nCreated both probability spreadsheets")

