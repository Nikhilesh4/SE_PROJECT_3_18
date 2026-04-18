#!/usr/bin/env python3
"""Quick test to verify research filter improvements."""

import sys
sys.path.insert(0, '/home/sanjana/Documents/6/SE/SE_PROJECT_3_18/backend')

from app.services.rss.filter import is_opportunity_post

# Test cases: (title, summary, should_pass)
test_cases = [
    # SHOULD PASS - Real opportunities with both signals
    (
        "PhD Fellowship in Machine Learning",
        "We are seeking PhD candidates. Application deadline: June 30, 2026. Apply now at...",
        True
    ),
    (
        "Postdoctoral Research Position",
        "Join our lab. We are recruiting postdocs. Submit your application by July 15.",
        True
    ),
    (
        "DAAD Scholarship for Master's Students",
        "Apply for the DAAD scholarship. Application deadline is May 31, 2026.",
        True
    ),
    (
        "Research Internship - Summer Program",
        "Call for applications for our summer research internship. Deadline: April 30.",
        True
    ),
    (
        "Faculty Position in Computer Science",
        "We are recruiting faculty members. Openings available in several areas.",
        True
    ),
    
    # SHOULD FAIL - Blog articles and advice
    (
        "How to Write a Research Paper: Tips and Tricks",
        "Learn how to write better research papers with these 10 tips...",
        False
    ),
    (
        "Top 5 Best Journals for Publishing AI Research",
        "Here are the top 5 journals where you should publish your AI research...",
        False
    ),
    (
        "Career Advice: Interview Tips for Researchers",
        "Get career advice on how to prepare for research interviews...",
        False
    ),
    (
        "How to Prepare for Your PhD Applications",
        "Tips on preparing for PhD applications and writing statements...",
        False
    ),
    (
        "What Makes a Good Research Paper?",
        "A complete guide to understanding what makes research papers good...",
        False
    ),
    (
        "My Journey as a PhD Student",
        "Today I want to share my personal experience as a PhD student and the lessons I learned...",
        False
    ),
    (
        "Key Differences Between PhD and Postdoc",
        "Guide explaining the difference between PhD and postdoctoral positions...",
        False
    ),
    
    # SHOULD FAIL - Missing application signals
    (
        "Research Fellowship Available",
        "A research fellowship opportunity is available in our lab.",
        False  # Has signal but no application info
    ),
    (
        "Scholarship for International Students",
        "Information about scholarships for international students.",
        False  # Has signal but no application info
    ),
]

print("Testing Research Filter Improvements")
print("=" * 60)

passed = 0
failed = 0

for i, (title, summary, expected) in enumerate(test_cases, 1):
    result = is_opportunity_post(title, summary, "research")
    status = "✓ PASS" if result == expected else "✗ FAIL"
    
    if result == expected:
        passed += 1
    else:
        failed += 1
    
    print(f"\n{i}. {status}")
    print(f"   Title: {title[:60]}...")
    print(f"   Expected: {expected}, Got: {result}")

print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed out of {len(test_cases)} tests")
