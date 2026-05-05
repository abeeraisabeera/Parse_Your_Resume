# Contributing to Resume Parser & Evaluator

Thank you for your interest in contributing! This document outlines the process for contributing to the project.

## Development Setup

```bash
# Fork and clone
git clone https://github.com/yourusername/resume-parser.git
cd resume-parser

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install pymupdf  # or pdfplumber

# Run tests
python test_resume_parser.py -v
```

## Adding Tests

All new features must include corresponding test cases in `test_resume_parser.py`. Follow the existing test class structure:

```python
class TestYourFeature(unittest.TestCase):
    def test_specific_behavior(self):
        result = rp.your_function(input_data)
        self.assertEqual(result, expected_output)
```

## Code Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Document functions with docstrings
- Keep functions focused and modular

## Pull Request Process

1. Ensure all tests pass: `python test_resume_parser.py`
2. Update documentation if needed
3. Add your changes to a feature branch
4. Submit PR with clear description of changes

## Reporting Issues

When reporting bugs, please include:
- Python version
- Sample resume text (anonymized) that triggers the issue
- Expected vs actual output
- Error traceback if applicable
