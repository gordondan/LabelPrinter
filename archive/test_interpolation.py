#!/usr/bin/env python3

"""
Test script for template variable interpolation logic
Tests the substitute_variables function with various patterns
"""

import re
from datetime import datetime

class InterpolationTester:
    def __init__(self):
        self.hot_template_words = {
            'TODAY': datetime.now().strftime('%B %d, %Y'),
            'DATE': datetime.now().strftime('%B %d, %Y'),
            'LONG-DATE-TIME': datetime.now().strftime('%A, %B %d, %Y at %I:%M %p'),
            'CURRENT-TIME': datetime.now().strftime('%I:%M %p'),
            'MESSAGE': '',
            'BORDER MESSAGE': ''
        }
        
    def sanitize_text(self, text):
        """Sanitize text to remove problematic characters for printing"""
        if not text:
            return text
            
        # Replace problematic characters that might cause encoding issues
        replacements = {
            ''': "'",  # Smart quote
            ''': "'",  # Smart quote  
            '"': '"',  # Smart quote
            '"': '"',  # Smart quote
            '–': '-',  # En dash
            '—': '-',  # Em dash
            '…': '...',  # Ellipsis
        }
        
        for old_char, new_char in replacements.items():
            text = text.replace(old_char, new_char)
        
        # Additional sanitization for font rendering issues
        text = text.replace('ü', 'u')  # Replace any umlauts that might creep in
        text = text.replace('ä', 'a')
        text = text.replace('ö', 'o')
        text = text.replace('ß', 'ss')
        
        # Normalize whitespace
        text = ' '.join(text.split())
            
        # Ensure only ASCII characters (remove any remaining non-ASCII)
        try:
            text = text.encode('ascii', 'replace').decode('ascii')
        except Exception:
            text = ''.join(char for char in text if ord(char) < 128 and (char.isprintable() or char.isspace()))
            
        return text

    def substitute_variables(self, template_content, variable_values):
        """Substitute variables in template content"""
        result = template_content
        
        # First substitute hot template words
        for var_name, var_value in variable_values.items():
            # Handle hot template words
            if var_name in self.hot_template_words and var_value == "":
                var_value = self.hot_template_words[var_name]
            elif var_name == "TODAY":
                var_value = datetime.now().strftime('%B %d, %Y') if var_value == "" else var_value
            elif var_name == "LONG-DATE-TIME":
                var_value = datetime.now().strftime('%A, %B %d, %Y at %I:%M %p') if var_value == "" else var_value
            elif var_name == "CURRENT-TIME":
                var_value = datetime.now().strftime('%I:%M %p') if var_value == "" else var_value
            elif var_name == "DATE":
                var_value = datetime.now().strftime('%B %d, %Y') if var_value == "" else var_value
            
            # Sanitize the variable value before substitution
            var_value = self.sanitize_text(var_value)
                
            pattern = r"\{\{" + re.escape(var_name) + r"\}\}"
            result = re.sub(pattern, var_value, result)
            
        return result
        
    def extract_variables(self, template_content):
        """Extract {{variable}} patterns from template content"""
        pattern = r'\{\{([^}]+)\}\}'
        variables = []
        
        for match in re.finditer(pattern, template_content):
            var_name = match.group(1).strip()
            if var_name not in variables:
                variables.append(var_name)
                
        return variables

def run_tests():
    tester = InterpolationTester()
    tests = [
        {
            'name': 'Simple message substitution',
            'template': '--message {{MESSAGE}}',
            'variables': {'MESSAGE': 'Hello World'},
            'expected': '--message Hello World'
        },
        {
            'name': 'Date substitution',
            'template': '--message {{DATE}}',
            'variables': {'DATE': ''},  # Should use hot template word
            'expected': f'--message {datetime.now().strftime("%B %d, %Y")}'
        },
        {
            'name': 'Multiple variables',
            'template': '--message {{MESSAGE}} --border-message {{DATE}}',
            'variables': {'MESSAGE': 'Test message', 'DATE': ''},
            'expected': f'--message Test message --border-message {datetime.now().strftime("%B %d, %Y")}'
        },
        {
            'name': 'Mixed text and variables',
            'template': '--message "{{MESSAGE}} on {{DATE}}"',
            'variables': {'MESSAGE': 'Meeting', 'DATE': ''},
            'expected': f'--message "Meeting on {datetime.now().strftime("%B %d, %Y")}"'
        },
        {
            'name': 'Special characters',
            'template': '--message {{MESSAGE}}',
            'variables': {'MESSAGE': 'Test with "quotes" and—dashes'},
            'expected': '--message Test with "quotes" and-dashes'
        },
        {
            'name': 'Unicode characters',
            'template': '--message {{MESSAGE}}',
            'variables': {'MESSAGE': 'Café with naïve'},
            'expected': '--message Caf? with na?ve'  # Should be sanitized
        },
        {
            'name': 'No variables',
            'template': '--message Simple text',
            'variables': {},
            'expected': '--message Simple text'
        },
        {
            'name': 'Variable not provided',
            'template': '--message {{MISSING}}',
            'variables': {},
            'expected': '--message {{MISSING}}'  # Should remain unchanged
        },
        {
            'name': 'Case sensitivity',
            'template': '--message {{message}}',
            'variables': {'MESSAGE': 'Test'},  # Different case
            'expected': '--message {{message}}'  # Should not match
        },
        {
            'name': 'Current time',
            'template': '--message "Meeting at {{CURRENT-TIME}}"',
            'variables': {'CURRENT-TIME': ''},
            'expected': f'--message "Meeting at {datetime.now().strftime("%I:%M %p")}"'
        }
    ]
    
    print("Running Template Interpolation Tests")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for i, test in enumerate(tests, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"Template: {test['template']}")
        print(f"Variables: {test['variables']}")
        
        # Extract variables from template
        variables = tester.extract_variables(test['template'])
        print(f"Extracted variables: {variables}")
        
        # Perform substitution
        result = tester.substitute_variables(test['template'], test['variables'])
        print(f"Result: {result}")
        print(f"Expected: {test['expected']}")
        
        # Check if result matches expected (allowing for some flexibility with time-based values)
        if result == test['expected']:
            print("[PASS]")
            passed += 1
        else:
            print("[FAIL]")
            failed += 1
            
    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("All tests passed!")
    else:
        print(f"WARNING: {failed} test(s) failed - review interpolation logic")
        
    return failed == 0

if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)