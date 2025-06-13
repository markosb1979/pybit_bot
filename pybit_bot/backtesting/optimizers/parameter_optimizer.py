#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Parameter Optimizer

Optimizes strategy parameters using grid search, genetic algorithms,
or Bayesian optimization to find optimal parameter combinations.
"""

import os
import json
import logging
import itertools
import random
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from concurrent.futures import ProcessPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class ParameterOptimizer:
    """
    Optimizes strategy parameters to find optimal combinations.
    
    Supports multiple optimization methods:
    - Grid Search: Exhaustive search over parameter space
    - Random Search: Random sampling of parameter space
    - Genetic Algorithm: Evolutionary optimization
    """
    
    def __init__(self, backtest_engine, config: Dict[str, Any]):
        """
        Initialize the parameter optimizer.
        
        Args:
            backtest_engine: Backtest engine instance
            config: Configuration dictionary
        """
        self.backtest_engine = backtest_engine
        self.config = config
        self.results_dir = config.get('results_dir', 'results/optimization')
        
        # Ensure results directory exists
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Optimization parameters
        self.method = config.get('method', 'grid')  # 'grid', 'random', 'genetic'
        self.metric = config.get('optimization_metric', 'sharpe_ratio')
        self.max_workers = config.get('max_workers', 1)
        self.iterations = config.get('iterations', 100)
        
        # Genetic algorithm parameters
        self.population_size = config.get('population_size', 20)
        self.generations = config.get('generations', 5)
        self.mutation_rate = config.get('mutation_rate', 0.1)
        self.crossover_rate = config.get('crossover_rate', 0.7)
    
    def optimize(self, strategy_class, parameter_space: Dict[str, List[Any]], 
                base_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run parameter optimization.
        
        Args:
            strategy_class: Strategy class to optimize
            parameter_space: Parameter space to search
            base_params: Base parameters for the strategy
            
        Returns:
            Dictionary with optimization results
        """
        start_time = time.time()
        logger.info(f"Starting parameter optimization with method: {self.method}")
        
        # Select optimization method
        if self.method == 'grid':
            results = self._grid_search(strategy_class, parameter_space, base_params)
        elif self.method == 'random':
            results = self._random_search(strategy_class, parameter_space, base_params)
        elif self.method == 'genetic':
            results = self._genetic_algorithm(strategy_class, parameter_space, base_params)
        else:
            logger.error(f"Unknown optimization method: {self.method}")
            return {
                'status': 'error',
                'message': f"Unknown optimization method: {self.method}",
                'elapsed_time': 0,
                'best_parameters': {},
                'best_metrics': {},
                'all_results': []
            }
        
        elapsed_time = time.time() - start_time
        
        # Sort results by optimization metric
        all_results = sorted(
            results, 
            key=lambda x: x['metrics'][self.metric] if self.metric in x['metrics'] else 0,
            reverse=True
        )
        
        # Get best result
        best_result = all_results[0] if all_results else None
        
        # Save results
        self._save_results({
            'status': 'success',
            'method': self.method,
            'strategy': strategy_class.__name__,
            'parameter_space': parameter_space,
            'base_params': base_params,
            'optimization_metric': self.metric,
            'elapsed_time': elapsed_time,
            'best_parameters': best_result['parameters'] if best_result else {},
            'best_metrics': best_result['metrics'] if best_result else {},
            'all_results': all_results
        })
        
        logger.info(f"Optimization completed in {elapsed_time:.2f}s with {len(results)} evaluations")
        
        if best_result:
            logger.info(f"Best parameters: {best_result['parameters']}")
            logger.info(f"Best {self.metric}: {best_result['metrics'].get(self.metric, 'N/A')}")
        
        return {
            'status': 'success',
            'elapsed_time': elapsed_time,
            'best_parameters': best_result['parameters'] if best_result else {},
            'best_metrics': best_result['metrics'] if best_result else {},
            'all_results': all_results
        }
    
    def _grid_search(self, strategy_class, parameter_space: Dict[str, List[Any]], 
                    base_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform grid search optimization.
        
        Args:
            strategy_class: Strategy class
            parameter_space: Parameter space to search
            base_params: Base parameters
            
        Returns:
            List of parameter combinations and results
        """
        # Generate all parameter combinations
        param_names = list(parameter_space.keys())
        param_values = list(parameter_space.values())
        combinations = list(itertools.product(*param_values))
        
        logger.info(f"Grid search: evaluating {len(combinations)} parameter combinations")
        
        # Run backtests in parallel
        results = self._run_parallel_backtests(
            strategy_class,
            param_names,
            combinations,
            base_params
        )
        
        return results
    
    def _random_search(self, strategy_class, parameter_space: Dict[str, List[Any]], 
                      base_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform random search optimization.
        
        Args:
            strategy_class: Strategy class
            parameter_space: Parameter space to search
            base_params: Base parameters
            
        Returns:
            List of parameter combinations and results
        """
        # Generate random parameter combinations
        param_names = list(parameter_space.keys())
        combinations = []
        
        for _ in range(self.iterations):
            combination = []
            for param_values in parameter_space.values():
                value = random.choice(param_values)
                combination.append(value)
            combinations.append(combination)
        
        logger.info(f"Random search: evaluating {len(combinations)} parameter combinations")
        
        # Run backtests in parallel
        results = self._run_parallel_backtests(
            strategy_class,
            param_names,
            combinations,
            base_params
        )
        
        return results
    
    def _genetic_algorithm(self, strategy_class, parameter_space: Dict[str, List[Any]], 
                          base_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform genetic algorithm optimization.
        
        Args:
            strategy_class: Strategy class
            parameter_space: Parameter space to search
            base_params: Base parameters
            
        Returns:
            List of parameter combinations and results
        """
        param_names = list(parameter_space.keys())
        param_values = list(parameter_space.values())
        
        # Initialize population
        population = []
        for _ in range(self.population_size):
            individual = []
            for param_vals in param_values:
                individual.append(random.choice(param_vals))
            population.append(individual)
        
        all_results = []
        
        # Run generations
        for generation in range(self.generations):
            logger.info(f"Genetic algorithm: generation {generation+1}/{self.generations}")
            
            # Evaluate current population
            generation_results = self._run_parallel_backtests(
                strategy_class,
                param_names,
                population,
                base_params
            )
            
            all_results.extend(generation_results)
            
            # Sort by fitness
            generation_results.sort(
                key=lambda x: x['metrics'][self.metric] if self.metric in x['metrics'] else 0,
                reverse=True
            )
            
            # Create new population
            if generation < self.generations - 1:
                new_population = []
                
                # Elitism: keep best individuals
                elite_count = max(1, int(self.population_size * 0.1))
                for i in range(elite_count):
                    if i < len(generation_results):
                        params = generation_results[i]['parameters']
                        individual = [params[name] for name in param_names]
                        new_population.append(individual)
                
                # Fill rest of population with crossover and mutation
                while len(new_population) < self.population_size:
                    # Selection (tournament selection)
                    parent1 = self._tournament_selection(generation_results)
                    parent2 = self._tournament_selection(generation_results)
                    
                    # Crossover
                    if random.random() < self.crossover_rate:
                        child1, child2 = self._crossover(parent1, parent2, param_names)
                    else:
                        child1, child2 = parent1.copy(), parent2.copy()
                    
                    # Mutation
                    child1 = self._mutate(child1, parameter_space, param_names)
                    child2 = self._mutate(child2, parameter_space, param_names)
                    
                    new_population.append([child1[name] for name in param_names])
                    
                    if len(new_population) < self.population_size:
                        new_population.append([child2[name] for name in param_names])
                
                population = new_population
        
        return all_results
    
    def _tournament_selection(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Tournament selection for genetic algorithm.
        
        Args:
            results: List of parameter combinations and results
            
        Returns:
            Selected individual
        """
        tournament_size = 3
        tournament = random.sample(results, min(tournament_size, len(results)))
        tournament.sort(
            key=lambda x: x['metrics'][self.metric] if self.metric in x['metrics'] else 0,
            reverse=True
        )
        return tournament[0]['parameters']
    
    def _crossover(self, parent1: Dict[str, Any], parent2: Dict[str, Any], 
                  param_names: List[str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Crossover operation for genetic algorithm.
        
        Args:
            parent1: First parent parameters
            parent2: Second parent parameters
            param_names: Parameter names
            
        Returns:
            Two child parameter dictionaries
        """
        child1 = {}
        child2 = {}
        
        crossover_point = random.randint(1, len(param_names) - 1)
        
        for i, name in enumerate(param_names):
            if i < crossover_point:
                child1[name] = parent1[name]
                child2[name] = parent2[name]
            else:
                child1[name] = parent2[name]
                child2[name] = parent1[name]
        
        return child1, child2
    
    def _mutate(self, individual: Dict[str, Any], parameter_space: Dict[str, List[Any]], 
               param_names: List[str]) -> Dict[str, Any]:
        """
        Mutation operation for genetic algorithm.
        
        Args:
            individual: Individual parameters
            parameter_space: Parameter space
            param_names: Parameter names
            
        Returns:
            Mutated individual
        """
        mutated = individual.copy()
        
        for name in param_names:
            if random.random() < self.mutation_rate:
                mutated[name] = random.choice(parameter_space[name])
        
        return mutated
    
    def _run_parallel_backtests(self, strategy_class, param_names: List[str], 
                               combinations: List[List[Any]], 
                               base_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Run backtests in parallel.
        
        Args:
            strategy_class: Strategy class
            param_names: Parameter names
            combinations: Parameter combinations
            base_params: Base parameters
            
        Returns:
            List of parameter combinations and results
        """
        results = []
        
        # Run in parallel if multiple workers
        if self.max_workers > 1:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                
                for combination in combinations:
                    # Create parameter dictionary
                    params = base_params.copy()
                    for i, name in enumerate(param_names):
                        params[name] = combination[i]
                    
                    # Submit backtest
                    future = executor.submit(
                        self._run_single_backtest,
                        strategy_class,
                        params
                    )
                    futures.append((future, params))
                
                # Collect results
                for i, (future, params) in enumerate(futures):
                    try:
                        result = future.result()
                        results.append({
                            'parameters': params,
                            'metrics': result['metrics']
                        })
                        
                        if (i + 1) % 10 == 0:
                            logger.info(f"Completed {i+1}/{len(futures)} backtests")
                    except Exception as e:
                        logger.error(f"Error in backtest: {str(e)}")
        
        # Run sequentially if single worker
        else:
            for i, combination in enumerate(combinations):
                # Create parameter dictionary
                params = base_params.copy()
                for j, name in enumerate(param_names):
                    params[name] = combination[j]
                
                # Run backtest
                try:
                    result = self._run_single_backtest(strategy_class, params)
                    results.append({
                        'parameters': params,
                        'metrics': result['metrics']
                    })
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"Completed {i+1}/{len(combinations)} backtests")
                except Exception as e:
                    logger.error(f"Error in backtest: {str(e)}")
        
        return results
    
    def _run_single_backtest(self, strategy_class, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single backtest.
        
        Args:
            strategy_class: Strategy class
            params: Strategy parameters
            
        Returns:
            Backtest results
        """
        # Create a copy of the backtest engine to avoid state issues
        engine_copy = self.backtest_engine
        
        # Run backtest
        result = engine_copy.run_backtest(strategy_class, params)
        
        return result
    
    def _save_results(self, results: Dict[str, Any]):
        """
        Save optimization results.
        
        Args:
            results: Optimization results
        """
        try:
            # Create filename
            strategy = results['strategy']
            method = results['method']
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            filename = f"opt_{strategy}_{method}_{timestamp}.json"
            file_path = os.path.join(self.results_dir, filename)
            
            # Save to file
            with open(file_path, 'w') as f:
                json.dump(results, f, indent=2)
                
            logger.info(f"Optimization results saved to {file_path}")
            
        except Exception as e:
            logger.exception(f"Error saving optimization results: {str(e)}")