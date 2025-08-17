#!/bin/bash
# Bash test script for DatePrinter
# Tests all months with varying day formats (single and double digit)

echo -e "\033[36mDatePrinter Monthly Test Script\033[0m"
echo -e "\033[36m===============================\033[0m"
echo ""

# Test today's date first
echo -e "\033[33mTesting today's date...\033[0m"
python3 DatePrinter/date_printer.py
sleep 2

# Test dates for each month - alternating between single and double digit days
declare -a test_dates=(
    "2024-01-05:January:5"
    "2024-01-15:January:15"
    "2024-02-08:February:8"
    "2024-02-28:February:28"
    "2024-03-03:March:3"
    "2024-03-31:March:31"
    "2024-04-01:April:1"
    "2024-04-30:April:30"
    "2024-05-09:May:9"
    "2024-05-25:May:25"
    "2024-06-07:June:7"
    "2024-06-20:June:20"
    "2024-07-04:July:4"
    "2024-07-17:July:17"
    "2024-08-02:August:2"
    "2024-08-22:August:22"
    "2024-09-06:September:6"
    "2024-09-19:September:19"
    "2024-10-08:October:8"
    "2024-10-31:October:31"
    "2024-11-01:November:1"
    "2024-11-24:November:24"
    "2024-12-09:December:9"
    "2024-12-25:December:25"
)

for test_entry in "${test_dates[@]}"; do
    IFS=':' read -r date month day <<< "$test_entry"
    echo ""
    echo -e "\033[32mTesting $month - Day $day (Date: $date)\033[0m"
    python3 DatePrinter/date_printer.py -d "$date"
    
    # Pause between prints to avoid overwhelming the printer
    sleep 3
done

echo ""
echo -e "\033[36mTest completed!\033[0m"
echo -e "\033[36mTotal labels printed: $((${#test_dates[@]} + 1))\033[0m"