#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# ================================================================================================ #
# Project    : DeepCTR: Deep Learning for CTR Prediction                                           #
# Version    : 0.1.0                                                                               #
# Filename   : /dal.py                                                                             #
# ------------------------------------------------------------------------------------------------ #
# Author     : John James                                                                          #
# Email      : john.james.ai.studio@gmail.com                                                      #
# URL        : https://github.com/john-james-ai/DeepCTR                                            #
# ------------------------------------------------------------------------------------------------ #
# Created    : Friday May 13th 2022 02:51:48 pm                                                    #
# Modified   : Sunday May 15th 2022 11:22:36 pm                                                    #
# ------------------------------------------------------------------------------------------------ #
# License    : BSD 3-clause "New" or "Revised" License                                             #
# Copyright  : (c) 2022 John James                                                                 #
# ================================================================================================ #
"""Module defines the API for data access and management."""
import os
from abc import ABC, abstractmethod
import logging
import logging.config
from dataclasses import dataclass
from typing import Any, Union
from difflib import get_close_matches
import shutil

from pyspark.sql import DataFrame

from deepctr.persistence.io import SparkCSV, SparkParquet, S3
from deepctr.utils.log_config import LOG_CONFIG

# ------------------------------------------------------------------------------------------------ #
logging.config.dictConfig(LOG_CONFIG)
logging.getLogger("py4j").setLevel(logging.WARN)
logger = logging.getLogger(__name__)
# ------------------------------------------------------------------------------------------------ #


# ------------------------------------------------------------------------------------------------ #
#                                DATA PARAMETER OBJECT                                             #
# ------------------------------------------------------------------------------------------------ #
@dataclass
class DataParam:
    name: str  # The name of the file.
    stage: str  # Data processing stage, i.e 'raw', 'staged', 'interim', 'clean', 'processed'
    dataset: str  # The specific data collection
    source: str  # data source, i.e. 'alibaba', 'criteo', 'avazu'
    bucket: str  # The name of the S3 bucket
    object: str  # The object key for an S3 resource
    home: str = "data"
    format: str = "parquet"  # Storage format, either 'csv', or 'parquet'
    force: bool = False  # Controls whether to override existing data


# ------------------------------------------------------------------------------------------------ #
#                                DATA ACCESS OBJECTS                                               #
# ------------------------------------------------------------------------------------------------ #


class DAO(ABC):
    """Defines interface for data access objects."""

    @abstractmethod
    def create(self, data_param: Any, data: Any, force: bool = False) -> None:
        pass

    @abstractmethod
    def read(self, data_param: Any) -> None:
        pass

    @abstractmethod
    def delete(self, data_param: Any) -> None:
        pass

    @abstractmethod
    def download(self, data_param: DataParam) -> None:
        pass

    @abstractmethod
    def _get_filepath(self, data_param: Any) -> str:
        pass


# ------------------------------------------------------------------------------------------------ #
#                                     DATA REPOSITORY                                              #
# ------------------------------------------------------------------------------------------------ #


class DataTableDAO(DAO):
    """Data access object for data tables."""

    __stages = ["raw", "staged", "interim", "clean", "processed", "extract"]
    __source = ["alibaba", "avazu", "criteo"]
    __formats = ["csv", "parquet"]

    # -------------------------------------------------------------------------------------------- #
    def create(self, data_param: DataParam, data: DataFrame, force: str = True) -> None:
        """Persists a new data table to storage.

        Args:
            data_param (DataParam): Data transfer object containing the datatable parameters
            data (DataFrame): The data to store
            force (bool): If True, method will overwrite existing data. Default is True

        """
        filepath = self._get_filepath(data_param)
        if os.path.exists(filepath) and not force:
            raise FileExistsError("{} already exists.".format(filepath))

        io = self._get_io(format=data_param.format)
        io.write(data=data, filepath=filepath)

    # -------------------------------------------------------------------------------------------- #
    def read(self, data_param: DataParam) -> DataFrame:
        """Obtains a DataFrame from persisted storage

        Args:
            data_param (DataParam): Data transfer object containing the datatable parameters

        Returns (DataFrame)
        """
        filepath = self._get_filepath(data_param)

        try:
            io = self._get_io(format=data_param.format)
            return io.read(filepath=filepath)
        except FileNotFoundError as e:
            logger.error("File {} not found.".format(filepath))
            raise FileNotFoundError(e)

    # -------------------------------------------------------------------------------------------- #
    def delete(self, data_param: DataParam) -> None:
        """Removes a data table from persisted storage

        Args:
            data_param (DataParam): Data transfer object containing the datatable parameters
        """
        filepath = self._get_filepath(data_param)
        shutil.rmtree(filepath, ignore_errors=True)

    # -------------------------------------------------------------------------------------------- #
    def download(self, data_param: DataParam) -> None:
        """Downloads data from an S3 Resource

        Args:
            data_param (DataParam): Data transfer object containing the datatable parameters
        """
        directory = self._get_directory(data_param)

        io = S3()
        io.download_directory(
            bucket=data_param.bucket,
            folder=data_param.folder,
            directory=directory,
            force=data_param.force,
        )

    # -------------------------------------------------------------------------------------------- #
    def _get_filepath(self, data_param: DataParam) -> str:
        try:
            source = get_close_matches(data_param.dataset, DataTableDAO.__source)[0]
            stage = get_close_matches(data_param.stage, DataTableDAO.__stages)[0]
            format = get_close_matches(data_param.format, DataTableDAO.__formats)[0]

        except IndexError as e:
            raise ValueError("Unable to parse dataset configuration. {}".format(e))
        return (
            os.path.join(data_param.home, source, data_param.dataset, stage, data_param.name)
            + "."
            + format
        )

    # -------------------------------------------------------------------------------------------- #
    def _get_directory(self, data_param: DataParam) -> str:
        try:
            source = get_close_matches(data_param.dataset, DataTableDAO.__source)[0]
            stage = get_close_matches(data_param.stage, DataTableDAO.__stages)[0]

        except IndexError as e:
            raise ValueError("Unable to parse dataset configuration. {}".format(e))
        return os.path.join(data_param.home, source, data_param.dataset, stage)

    # -------------------------------------------------------------------------------------------- #
    def _get_io(self, format: str) -> Union[SparkCSV, SparkParquet]:
        if "csv" in format:
            io = SparkCSV()
        else:
            io = SparkParquet()
        return io
