'use strict'

const { compatibleSortPreference } = require('./compat.cjs')

function sanitizePreferences(value) {
  const result = {}
  if (!value || typeof value !== 'object' || Array.isArray(value)) return result
  if (['light', 'dark'].includes(value.theme)) result.theme = value.theme
  const sort = compatibleSortPreference(value)
  if (['', 'created_asc', 'created_desc', 'alpha_asc', 'alpha_desc'].includes(sort)) {
    result['vocove-word-sort'] = sort
  }
  return result
}

module.exports = { sanitizePreferences }
