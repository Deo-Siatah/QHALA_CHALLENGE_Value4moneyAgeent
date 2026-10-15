import re
from pathlib import Path
from typing import List, Dict, Any
import pypdf
from pydantic import BaseModel, Field, validator
from config import settings


class BidParseError(ValueError):
    """Exception raised when bid parsing fails."""
    pass


class Item(BaseModel):
    no: int
    description: str
    unit: str
    quantity: float
    unit_price: float
    line_total: float


class BidResult(BaseModel):
    bidder: str
    tender_ref: str
    currency: str
    items: List[Item]
    stated_total: float
    computed_total: float
    arithmetic_ok: bool
    issues: List[str]


def parse_bid(path: Path, bids_dir: Path) -> Dict[str, Any]:
    """
    Parse a bid PDF file and return structured data.
    
    Args:
        path: Path to the bid PDF file
        bids_dir: Base directory for bids (for path validation)
    
    Returns:
        Dictionary with bid data and arithmetic validation
        
    Raises:
        BidParseError: For invalid input, missing fields, or malformed data
    """
    # Validate path security
    if path.is_absolute():
        resolved_path = path.resolve()
        bids_dir_resolved = bids_dir.resolve()
        if not str(resolved_path).startswith(str(bids_dir_resolved)):
            raise BidParseError("Path outside bids directory")
        check_path = resolved_path
    else:
        # For relative paths, resolve against bids_dir
        resolved_path = (bids_dir / path).resolve()
        bids_dir_resolved = bids_dir.resolve()
        if not str(resolved_path).startswith(str(bids_dir_resolved)):
            raise BidParseError("Path outside bids directory")
        check_path = resolved_path
    
    # Check if file exists
    if not check_path.exists():
        raise BidParseError("File not found")
    
    # Extract text from PDF
    try:
        with open(check_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            if len(pdf_reader.pages) == 0:
                raise BidParseError("PDF has no pages")
            
            lines = []
            for page in pdf_reader.pages:
                text = page.extract_text()
                if not text:
                    raise BidParseError("Unable to extract text from PDF")
                lines.extend(text.split('\n'))
    except Exception as e:
        raise BidParseError(f"Unable to extract text from PDF: {str(e)}")
    
    # Process lines and extract data
    processed_lines = []
    for line in lines:
        line = line.strip()
        if line:  # Ignore empty lines
            processed_lines.append(line)
    
    # Extract required fields
    fields = {}
    required_labels = ['Bidder:', 'Tender reference:', 'Currency:', 'Stated total:']
    
    for label in required_labels:
        matches = [line for line in processed_lines if line.lower().startswith(label.lower())]
        if len(matches) == 0:
            raise BidParseError(f"Missing required field: {label[:-1]}")
        if len(matches) > 1:
            raise BidParseError(f"Duplicate label found: {label[:-1]}")
        fields[label[:-1]] = matches[0][len(label):].strip()
    
    # Parse items
    items = []
    item_pattern = r'^(\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*([0-9,]+\.?\d*)\s*\|\s*([0-9,]+\.?\d*)\s*\|\s*([0-9,]+\.?\d*)$'
    
    for line in processed_lines:
        match = re.match(item_pattern, line)
        if match:
            try:
                no = int(match.group(1))
                description = match.group(2).strip()
                unit = match.group(3).strip()
                quantity = parse_number(match.group(4))
                unit_price = parse_number(match.group(5))
                line_total = parse_number(match.group(6))
                
                # Validate numbers
                if quantity <= 0:
                    raise ValueError("Quantity must be > 0")
                if unit_price <= 0:
                    raise ValueError("Unit price must be > 0")
                if line_total < 0:
                    raise ValueError("Line total must be >= 0")
                
                items.append(Item(
                    no=no,
                    description=description,
                    unit=unit,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total
                ))
            except ValueError as e:
                raise BidParseError(f"Invalid number format: {str(e)}")
        elif re.match(r'^\d+\s*\|', line):  # Looks like an item but malformed
            raise BidParseError(f'Malformed item row: "{line}"')
    
    if not items:
        raise BidParseError("No items found")
    
    # Validate currency
    if fields['Currency'].upper() != 'KES':
        raise BidParseError("Currency must be KES")
    
    # Calculate totals and check arithmetic
    computed_total = round(sum(item.quantity * item.unit_price for item in items), 2)
    stated_total = parse_number(fields['Stated total'])
    
    issues = []
    arithmetic_ok = True
    
    # Check item line totals
    for i, item in enumerate(items, 1):
        expected_total = item.quantity * item.unit_price
        if abs(expected_total - item.line_total) > 0.01:
            issues.append(f"Line {i}: {int(item.quantity)} x {int(item.unit_price)} = {expected_total:.2f} but line total is {item.line_total:.2f}")
            arithmetic_ok = False
    
    # Check stated total
    if abs(computed_total - stated_total) > 0.01:
        issues.append(f"Stated total {stated_total:.2f} does not match computed total {computed_total:.2f}")
        arithmetic_ok = False
    
    return {
        'bidder': fields['Bidder'],
        'tender_ref': fields['Tender reference'],
        'currency': fields['Currency'],
        'items': [item.model_dump() for item in items],
        'stated_total': stated_total,
        'computed_total': round(computed_total, 2),
        'arithmetic_ok': arithmetic_ok,
        'issues': issues
    }


def parse_bid_pdf(path: str) -> Dict[str, Any]:
    """
    MCP wrapper for parse_bid function.
    
    Args:
        path: Path to the bid PDF file (relative to bids_dir or absolute)
    
    Returns:
        Dictionary with bid data and arithmetic validation
    """
    from config import settings
    return parse_bid(Path(path), settings.bids_dir)


def parse_number(number_str: str) -> float:
    """Parse a number string with optional commas and decimals."""
    # Remove commas
    clean_str = number_str.replace(',', '')
    
    # Check for valid number format
    if not re.match(r'^[0-9]*\.?[0-9]+$', clean_str):
        raise ValueError("Invalid number format")
    
    return float(clean_str)