#!/usr/bin/env python3
"""
Play the Guess Votes game for ballot anonymization testing.

First, generate test case

Creates:
1. A CVR file with ballots in different styles
2. A parallel spreadsheet showing voter probabilities for each candidate
"""

import csv

# Test case configuration
# 1 ballot in style 1R1 (rare, contest A only)
# 10 ballots in style 2S2 (common, contests A and B)
# 10 ballots in style 1S3 (common, contest B only)

# Contest A: A0, A1
# Contest B: B0, B1

# Create CVR file
def create_cvr_file():
    """Create the CVR test file."""
    
    # Line 1: Version/Election name
    version = ["Test Election 2024", "5.10.50.85"]
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
        "counting_group": "Vote by Mail",
        "precinct": "1R1",
        "ballot_type": "1 (1)",
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
            "counting_group": "Vote by Mail",
            "precinct": "2S2",
            "ballot_type": "2 (2)",
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
            "counting_group": "Vote by Mail",
            "precinct": "1S3",
            "ballot_type": "1 (3)",
            "votes": ["", "", vote_b, vote_b_alt]  # No A contest
        })
    
    # Write CVR file
    with open("test_case_cvr.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
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

def create_probability_spreadsheet(ballots):
    """Create the probability spreadsheet showing what analysts can deduce."""
    
    # Calculate overall election results
    total_votes_a0 = 0
    total_votes_a1 = 0
    total_votes_b0 = 0
    total_votes_b1 = 0
    total_eligible_a = 0  # Ballots that could vote on A
    total_eligible_b = 0  # Ballots that could vote on B
    
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
    
    # Calculate probabilities
    prob_a0 = total_votes_a0 / total_eligible_a if total_eligible_a > 0 else 0.0
    prob_a1 = total_votes_a1 / total_eligible_a if total_eligible_a > 0 else 0.0
    prob_undervote_a = 1.0 - prob_a0 - prob_a1
    
    prob_b0 = total_votes_b0 / total_eligible_b if total_eligible_b > 0 else 0.0
    prob_b1 = total_votes_b1 / total_eligible_b if total_eligible_b > 0 else 0.0
    prob_undervote_b = 1.0 - prob_b0 - prob_b1
    
    # Format probabilities to 4 significant digits
    def format_prob(p):
        if p == 0.0:
            return "0.0000"
        # Use 4 significant digits
        return f"{p:.4g}".ljust(6, "0")[:6]
    
    # Create spreadsheet
    with open("test_case_probabilities.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        # Headers
        writer.writerow(["Voter", "Style", "A0", "A1", "B0", "B1"])
        
        # One row per voter
        for i, ballot in enumerate(ballots, 1):
            voter_name = f"V{i}"
            style = ballot["precinct"]
            votes = ballot["votes"]
            
            # Determine probabilities based on what contests appear on ballot
            if votes[0] != "" or votes[1] != "":  # Contest A on ballot
                p_a0 = format_prob(prob_a0)
                p_a1 = format_prob(prob_a1)
            else:
                p_a0 = ""  # Contest not on ballot
                p_a1 = ""
            
            if votes[2] != "" or votes[3] != "":  # Contest B on ballot
                p_b0 = format_prob(prob_b0)
                p_b1 = format_prob(prob_b1)
            else:
                p_b0 = ""  # Contest not on ballot
                p_b1 = ""
            
            writer.writerow([voter_name, style, p_a0, p_a1, p_b0, p_b1])
    
    print(f"Election results:")
    print(f"  Contest A: A0={total_votes_a0}/{total_eligible_a} ({prob_a0:.4f}), A1={total_votes_a1}/{total_eligible_a} ({prob_a1:.4f}), Undervote={prob_undervote_a:.4f}")
    print(f"  Contest B: B0={total_votes_b0}/{total_eligible_b} ({prob_b0:.4f}), B1={total_votes_b1}/{total_eligible_b} ({prob_b1:.4f}), Undervote={prob_undervote_b:.4f}")

if __name__ == "__main__":
    ballots = create_cvr_file()
    print(f"Created CVR file with {len(ballots)} ballots")
    create_probability_spreadsheet(ballots)
    print("Created probability spreadsheet")

