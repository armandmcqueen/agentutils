# Changelog

## v2.1.0

- Added cursor-based pagination to all list endpoints
- New `role` field on user objects
- Rate limit headers now included in all responses

## v2.0.0

- **Breaking:** Authentication switched from query parameter to Bearer token
- **Breaking:** Response envelope changed from `{"users": [...]}` to `{"data": [...]}`
- Added rate limiting (100 req/min per key)

## v1.0.0

- Initial release with user CRUD endpoints
