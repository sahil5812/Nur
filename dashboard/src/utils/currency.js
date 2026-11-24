// src/utils/currency.js — Dynamic Currency Formatter based on Account & Country

export const CURRENCY_MAP = {
  USD: { symbol: '$', name: 'US Dollar', locale: 'en-US' },
  INR: { symbol: '₹', name: 'Indian Rupee', locale: 'en-IN' },
  EUR: { symbol: '€', name: 'Euro', locale: 'de-DE' },
  GBP: { symbol: '£', name: 'British Pound', locale: 'en-GB' },
  JPY: { symbol: '¥', name: 'Japanese Yen', locale: 'ja-JP' },
  AED: { symbol: 'AED ', name: 'UAE Dirham', locale: 'ar-AE' },
  CAD: { symbol: 'C$', name: 'Canadian Dollar', locale: 'en-CA' },
  AUD: { symbol: 'A$', name: 'Australian Dollar', locale: 'en-AU' },
  CHF: { symbol: 'CHF ', name: 'Swiss Franc', locale: 'de-CH' },
  SGD: { symbol: 'S$', name: 'Singapore Dollar', locale: 'en-SG' },
};

/**
 * Returns the currency symbol for the given 3-letter currency code (e.g. 'INR' -> '₹')
 */
export function getCurrencySymbol(currencyCode) {
  if (!currencyCode) return '₹';
  const upper = String(currencyCode).toUpperCase();
  return CURRENCY_MAP[upper]?.symbol || (upper + ' ');
}

/**
 * Formats a monetary amount dynamically into the account's local currency.
 * e.g. formatCurrency(5000, 'INR') -> "₹5,000.00"
 *      formatCurrency(250.5, 'INR', true) -> "+₹250.50"
 *      formatCurrency(-150, 'INR', true) -> "-₹150.00"
 */
export function formatCurrency(amount, currencyCode = 'INR', includeSign = false) {
  const num = Number(amount || 0);
  const symbol = getCurrencySymbol(currencyCode);
  const isPos = num > 0;
  const isNeg = num < 0;
  const locale = CURRENCY_MAP[String(currencyCode).toUpperCase()]?.locale || 'en-IN';

  const absFormatted = Math.abs(num).toLocaleString(locale, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  if (includeSign) {
    if (isPos) return `+${symbol}${absFormatted}`;
    if (isNeg) return `-${symbol}${absFormatted}`;
    return `${symbol}0.00`;
  }
  return `${symbol}${absFormatted}`;
}
