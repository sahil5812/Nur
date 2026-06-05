// src/utils/validation.js

export const validateEmail = (email) => {
  if (!email) {
    return { valid: false, error: "Email is required" };
  }

  // Check 1: Basic format (has @ and .)
  const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  if (!emailRegex.test(email)) {
    return { valid: false, error: "Invalid email format" };
  }
  
  // Check 2: No spaces
  if (email.includes(' ')) {
    return { valid: false, error: "Email cannot contain spaces" };
  }
  
  // Check 3: Valid domain extensions
  const validTLDs = ['com', 'net', 'org', 'in', 'io', 'co', 'edu', 'gov'];
  const tld = email.split('.').pop().toLowerCase();
  if (!validTLDs.includes(tld)) {
    return { valid: false, error: "Invalid email domain extension" };
  }
  
  return { valid: true, error: null };
};

export const validatePassword = (password) => {
  const errors = [];
  
  if (!password || password.length < 8) {
    errors.push("At least 8 characters");
  }
  if (!password || !/[A-Z]/.test(password)) {
    errors.push("At least 1 uppercase letter");
  }
  if (!password || !/[0-9]/.test(password)) {
    errors.push("At least 1 number");
  }
  if (!password || !/[!@#$%^&*]/.test(password)) {
    errors.push("At least 1 special character (!@#$%^&*)");
  }
    
  let strength = 'Weak';
  if (errors.length === 0) {
    strength = 'Strong';
  } else if (errors.length <= 2) {
    strength = 'Medium';
  }

  return {
    valid: errors.length === 0,
    errors: errors,
    strength: strength
  };
};

export const validatePasswordMatch = (password, confirmPassword) => {
  return {
    valid: password === confirmPassword,
    error: password !== confirmPassword ? "Passwords do not match" : null
  };
};
