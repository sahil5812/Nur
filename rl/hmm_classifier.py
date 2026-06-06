"""
rl/hmm_classifier.py — Native Gaussian Hidden Markov Model Classifier.

Implements Expectation-Maximization (Baum-Welch) learning and Viterbi state 
decoding for diagonal covariance Gaussian emissions. Zero external C-dependencies.
"""

import json
from pathlib import Path
import numpy as np


class GaussianHMM:
    """Hidden Markov Model with Gaussian emissions (diagonal covariance).

    Attributes:
        n_states: Number of hidden states (e.g. 2: Ranging vs. Trending).
        n_features: Number of input features.
        transmat: Transition probability matrix (shape: n_states x n_states).
        startprob: Initial state distribution (shape: n_states).
        means: State emission means (shape: n_states x n_features).
        covars: State emission diagonal covariances (shape: n_states x n_features).
    """

    def __init__(self, n_states: int = 2) -> None:
        self.n_states: int = n_states
        self.n_features: int | None = None
        self.transmat: np.ndarray | None = None
        self.startprob: np.ndarray | None = None
        self.means: np.ndarray | None = None
        self.covars: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Emission probability calculation
    # ------------------------------------------------------------------
    def _pdf(self, x: np.ndarray, state: int) -> float:
        """Compute Gaussian probability density function for diagonal covariance."""
        mean = self.means[state]
        cov = self.covars[state]
        # Avoid division by zero
        cov = np.maximum(cov, 1e-6)
        
        diff = x - mean
        exponent = -0.5 * np.sum((diff ** 2) / cov)
        denom = np.prod(np.sqrt(2 * np.pi * cov))
        return float(np.exp(exponent) / (denom + 1e-12))

    def _get_emissions(self, X: np.ndarray) -> np.ndarray:
        """Compute emission probabilities matrix (shape: T x n_states)."""
        T = X.shape[0]
        B = np.zeros((T, self.n_states))
        for t in range(T):
            for s in range(self.n_states):
                B[t, s] = self._pdf(X[t], s)
        return np.maximum(B, 1e-100)  # floor to prevent float underflow

    # ------------------------------------------------------------------
    # Forward-Backward algorithm (with scaling to prevent underflow)
    # ------------------------------------------------------------------
    def _forward(self, B: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        T = B.shape[0]
        alpha = np.zeros((T, self.n_states))
        c = np.zeros(T)  # Scaling coefficients

        # Initialization
        alpha[0] = self.startprob * B[0]
        c[0] = 1.0 / (np.sum(alpha[0]) + 1e-12)
        alpha[0] *= c[0]

        # Induction
        for t in range(1, T):
            alpha[t] = np.dot(alpha[t - 1], self.transmat) * B[t]
            c[t] = 1.0 / (np.sum(alpha[t]) + 1e-12)
            alpha[t] *= c[t]

        return alpha, c

    def _backward(self, B: np.ndarray, c: np.ndarray) -> np.ndarray:
        T = B.shape[0]
        beta = np.zeros((T, self.n_states))

        # Initialization
        beta[T - 1] = 1.0 * c[T - 1]

        # Induction
        for t in range(T - 2, -1, -1):
            beta[t] = np.dot(self.transmat, B[t + 1] * beta[t + 1]) * c[t]

        return beta

    # ------------------------------------------------------------------
    # Fit (Baum-Welch / EM training)
    # ------------------------------------------------------------------
    def fit(self, X: np.ndarray, max_iter: int = 30, tol: float = 1e-4) -> "GaussianHMM":
        """Fit the model parameters to observations using Baum-Welch algorithm."""
        T, self.n_features = X.shape

        # Initialize parameters randomly/heuristically
        np.random.seed(42)
        self.startprob = np.full(self.n_states, 1.0 / self.n_states)
        self.transmat = np.full((self.n_states, self.n_states), 1.0 / self.n_states)
        
        # Partition data into chunks to initialize means
        split_idx = T // self.n_states
        self.means = np.array([np.mean(X[i*split_idx:(i+1)*split_idx], axis=0) for i in range(self.n_states)])
        self.covars = np.array([np.var(X[i*split_idx:(i+1)*split_idx], axis=0) + 1e-2 for i in range(self.n_states)])

        last_log_lik = -np.inf

        for iteration in range(max_iter):
            # 1. E-Step: Calculate emission probability grid
            B = self._get_emissions(X)
            
            # Forward & Backward runs
            alpha, c = self._forward(B)
            beta = self._backward(B, c)

            # Log-likelihood computation
            log_lik = -np.sum(np.log(c + 1e-100))

            # Check convergence
            if abs(log_lik - last_log_lik) < tol:
                break
            last_log_lik = log_lik

            # Compute posteriors (gamma and xi)
            # gamma_t(i) = alpha_t(i) * beta_t(i) / scaling
            gamma = alpha * beta
            # Normalize over states at each step
            gamma = gamma / (np.sum(gamma, axis=1, keepdims=True) + 1e-12)

            # Compute xi: transition densities
            # xi_t(i,j) = alpha_t(i) * A_ij * B_t+1(j) * beta_t+1(j)
            xi = np.zeros((T - 1, self.n_states, self.n_states))
            for t in range(T - 1):
                denom = np.sum(alpha[t])
                for i in range(self.n_states):
                    for j in range(self.n_states):
                        xi[t, i, j] = alpha[t, i] * self.transmat[i, j] * B[t + 1, j] * beta[t + 1, j]
                # Normalize xi[t]
                denom = np.sum(xi[t])
                if denom > 0:
                    xi[t] /= denom

            # 2. M-Step: Re-estimate model parameters
            # startprob
            self.startprob = gamma[0] / np.sum(gamma[0])

            # transmat
            sum_xi = np.sum(xi, axis=0)
            sum_gamma_t1 = np.sum(gamma[:-1], axis=0, keepdims=True).T
            self.transmat = sum_xi / (sum_gamma_t1 + 1e-12)
            # Normalize rows
            self.transmat /= np.sum(self.transmat, axis=1, keepdims=True)

            # Means & Covariances
            sum_gamma = np.sum(gamma, axis=0, keepdims=True).T
            for s in range(self.n_states):
                w = gamma[:, s]
                sum_w = np.sum(w) + 1e-12
                self.means[s] = np.sum(X * w[:, np.newaxis], axis=0) / sum_w
                
                diff = X - self.means[s]
                self.covars[s] = np.sum((diff ** 2) * w[:, np.newaxis], axis=0) / sum_w + 1e-4

        # Force state sorting: ensure State 0 has lower mean ATR (index 1 feature) than State 1
        if self.means is not None and self.means.shape[0] == 2:
            if self.means[0, 1] > self.means[1, 1]:
                self.startprob = self.startprob[::-1]
                self.transmat = self.transmat[::-1, ::-1]
                self.means = self.means[::-1]
                self.covars = self.covars[::-1]

        return self

    # ------------------------------------------------------------------
    # Viterbi Algorithm (predict sequence of hidden states)
    # ------------------------------------------------------------------
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Decode the most probable hidden state sequence for X using Viterbi."""
        T = X.shape[0]
        B = self._get_emissions(X)
        
        # Log space calculations to prevent numerical underflow
        log_start = np.log(self.startprob + 1e-100)
        log_trans = np.log(self.transmat + 1e-100)
        log_emiss = np.log(B + 1e-100)

        # DP tables
        viterbi_table = np.zeros((T, self.n_states))
        backpointer = np.zeros((T, self.n_states), dtype=int)

        # Initialize
        viterbi_table[0] = log_start + log_emiss[0]

        # Induction
        for t in range(1, T):
            for s in range(self.n_states):
                prev_probs = viterbi_table[t - 1] + log_trans[:, s]
                best_prev_state = int(np.argmax(prev_probs))
                viterbi_table[t, s] = prev_probs[best_prev_state] + log_emiss[t, s]
                backpointer[t, s] = best_prev_state

        # Termination & Backtracking
        states = np.zeros(T, dtype=int)
        states[T - 1] = int(np.argmax(viterbi_table[T - 1]))
        for t in range(T - 2, -1, -1):
            states[t] = backpointer[t + 1, states[t + 1]]

        return states

    # ------------------------------------------------------------------
    # Save & Load Parameters (JSON Serialization)
    # ------------------------------------------------------------------
    def save(self, file_path: Path | str) -> None:
        """Write model parameters to a JSON file."""
        data = {
            "n_states": self.n_states,
            "n_features": self.n_features,
            "startprob": self.startprob.tolist() if self.startprob is not None else None,
            "transmat": self.transmat.tolist() if self.transmat is not None else None,
            "means": self.means.tolist() if self.means is not None else None,
            "covars": self.covars.tolist() if self.covars is not None else None,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self, file_path: Path | str) -> "GaussianHMM":
        """Load model parameters from a JSON file."""
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.n_states = data["n_states"]
        self.n_features = data["n_features"]
        self.startprob = np.array(data["startprob"]) if data["startprob"] is not None else None
        self.transmat = np.array(data["transmat"]) if data["transmat"] is not None else None
        self.means = np.array(data["means"]) if data["means"] is not None else None
        self.covars = np.array(data["covars"]) if data["covars"] is not None else None
        return self
