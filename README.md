# Lease Doc PDF Parser 

This code parses lease records and converts it into JSON

## Prerequisites
Before you begin, ensure you have met the following requirements:

Python (version 3.11 or above)
Poetry for dependency management and packaging.

## Installation
To install the project dependencies, follow these steps:

```bash
brew install poetry go-task
```

Usage
To run the project:

1. Run `task install`
2. Run `task run` -> This will spin up a uvicorn webserver with a fastapi instance running

Example curl command
Make sure to replace /path/to/pdf_file.pdf with a real path on your file system pointing to your lease document
```
curl --location 'http://127.0.0.1:8000/documents/upload/lease' \
--form 'pdf=@"/path/to/pdf_file.pdf'
```

## Formatting Code
To format the codebase, ensuring it adheres to Python's coding standards, run `task format`


This command runs isort to sort your imports alphabetically and grouped together, followed by black to ensure your code is formatted according to PEP 8.


# Design

LeaseParser (Class)
(1) marshal_lease_data
    - The public method that receives a pdf and returns a list of pydantic records
(2) extract_lease_records
    - The private method that extracts rows from raw pdf data 

(3) define_column_mapings
    - The private method that gets the positions of the columns by using the first row
    
(4) map_row_to_columns
    - The private method that takes the positions from the define_columns_mappings and uses it to extract and plot the words along each new-line delimeted row



