# Changelog

## Version 0.2
* Rename readonly_fields to exclude_fields and exclude these fields from the `__eq__`
model method. This is usefull because the library knows which object are equal
depending on specific fields.
* BUG: Fix multiple update at update_or_create manager method. More specific,
fix calculation of the udpate_companies, add_companies and delete_companies.

## Version 0.1
* Basic lather client.
* Nav lather client.
