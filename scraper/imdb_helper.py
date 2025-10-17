#!/usr/bin/env python3
"""
IMDb Helper
Searches IMDb for movie information including ratings and duration
"""

import re
from typing import Optional, Dict
from imdb import Cinemagoer


class IMDbHelper:
    """Helper class to fetch movie data from IMDb"""

    def __init__(self):
        self.ia = Cinemagoer()

    def _parse_runtime(self, runtime_list: list) -> Optional[int]:
        """
        Parse runtime from technical data

        Args:
            runtime_list: List of runtime strings from IMDb

        Returns:
            Duration in minutes, or None if not found
        """
        if not runtime_list:
            return None

        for runtime_str in runtime_list:
            match = re.search(r'\((\d+)\s*min\)', runtime_str)
            if match:
                return int(match.group(1))

        return None

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        Search for a movie by title and optionally year, return rating and duration

        Args:
            title: Movie title to search for
            year: Optional year to narrow search

        Returns:
            Dictionary with 'rating' and 'duration' keys, or None if not found
        """
        try:
            results = self.ia.search_movie(title)

            if not results:
                print(f"No IMDb results found for: {title}")
                return None

            movie = results[0]

            if year:
                for result in results:
                    if result.get('year') == year:
                        movie = result
                        break

            movie_id = movie.movieID
            self.ia.update(movie, info=['main', 'technical'])

            rating = movie.get('rating')

            tech = movie.get('tech', {})
            runtime_list = tech.get('runtime', []) if isinstance(tech, dict) else []
            duration_minutes = self._parse_runtime(runtime_list)

            result = {
                'rating': rating if rating else None,
                'duration': duration_minutes
            }

            print(f"IMDb data for '{title}' ({year or movie.get('year', 'N/A')}): Rating={rating}, Duration={duration_minutes}min")
            return result

        except Exception as e:
            print(f"Error fetching IMDb data for '{title}': {e}")
            return None

    def get_movie_info(self, title: str, year: Optional[int] = None) -> Dict[str, Optional[str]]:
        """
        Get movie information formatted for CSV storage

        Args:
            title: Movie title to search for
            year: Optional year to narrow search

        Returns:
            Dictionary with 'rating' and 'duration' as strings
        """
        data = self.search_movie(title, year)

        if not data:
            return {'rating': '', 'duration': ''}

        rating_str = f"{data['rating']:.1f}" if data['rating'] else ''
        duration_str = str(data['duration']) if data['duration'] else ''

        return {
            'rating': rating_str,
            'duration': duration_str
        }
