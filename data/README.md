# Data Directory

This directory contains input data and taxonomy files for local development and testing.

## Structure

- `taxonomy/` - Classification taxonomy dictionary (Spend_Taxonomy.xlsx)
- `samples/` - Sample input files for testing

## Note

All files in this directory are excluded from git and Azure Functions deployment.
Data is provided to the Azure Function via HTTP request body.
