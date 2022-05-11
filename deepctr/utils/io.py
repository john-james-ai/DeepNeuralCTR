#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# ================================================================================================ #
# Project  : Deepctr: Deep Learning for Conversion Rate Prediction                                 #
# Version  : 0.1.0                                                                                 #
# File     : /io.py                                                                                #
# Language : Python 3.8.12                                                                         #
# ------------------------------------------------------------------------------------------------ #
# Author   : John James                                                                            #
# Email    : john.james.ai.studio@gmail.com                                                        #
# URL      : https://github.com/john-james-ai/ctr                                                  #
# ------------------------------------------------------------------------------------------------ #
# Created  : Saturday, February 26th 2022, 6:41:17 pm                                              #
# Modified : Tuesday, May 3rd 2022, 8:48:33 pm                                                     #
# Modifier : John James (john.james.ai.studio@gmail.com)                                           #
# ------------------------------------------------------------------------------------------------ #
# License  : BSD 3-clause "New" or "Revised" License                                               #
# Copyright: (c) 2022 Bryant St. Labs                                                              #
# ================================================================================================ #
"""Reading and writing dataframes with progress bars"""
from abc import ABC, abstractmethod
import os
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from tqdm import tqdm
import yaml
import yamlordereddictloader
import pyspark
import findspark
from pyspark import SparkContext, SparkConf
from pyspark.sql import SparkSession
from typing import Any

findspark.init()

# ------------------------------------------------------------------------------------------------ #


class IO(ABC):
    """Base class for IO classes"""

    @abstractmethod
    def read(self, filepath: str, **kwargs) -> pd.DataFrame:
        pass

    @abstractmethod
    def write(self, data: Any, filepath: str, **kwargs) -> None:
        pass


# ------------------------------------------------------------------------------------------------ #


class Parquet(IO):
    """Reads, and writes Spark DataFrames to / from Parquet storage format.."""

    def read(self, filepath: str, memory: int = 80, cores: int = 18, **kwargs) -> pyspark.sql.DataFrame:
        """Reads a Spark DataFrame from Parquet file resource

        Args:
            filepath (str): The path to the parquet file resource
            memory (int): The gb of memory allocated to each executor. Defaults to 90Gb
            cores (int): The number of cores allocated to each executor. Defaults to 18 cores.            

        Returns:
            Spark DataFrame
        """
        # Format resource configuration 
        cores = self._get_cores(cores)
        memory = self._get_memory(memory)

        # Set resources available.
        conf = SparkConf().setAll([('spark.executor.memory', memory),('spark.executor.cores',cores)])
        
        # Create spark session
        spark = SparkSession.builder.config(conf=conf).appName("Read Parquet").getOrCreate()
        
        # Read the data
        sdf = spark.read.parquet(filepath)
        spark.stop()
        return sdf


    def write(self, data: pyspark.sql.DataFrame, filepath: str, header: bool = True, 
        partition_by: list = None, mode: str = "overwrite", **kwargs) -> None:
        """Writes Spark DataFrame to Parquet file resource

        Args:
            data (pyspark.sql.DataFrame): Spark DataFrame to write
            filepath (str): The path to the parquet file to be written
            partition_by (list): List of strings containing partition column names  
            mode (str): 'overwrite' or 'append'. Default is 'overwrite'.
        """

        if partition_by is None:
            data.write.option("header", header) \
                    .mode(mode) \
                    .parquet(filepath)

        else:
            data.write.option("header", header) \
                    .partitionBy(partition_by) \
                    .mode(mode) \
                    .parquet(filepath)


    def _get_memory(self, memory: int = 90) -> int:
        """Returns the number of gigabytes of memory to be allocated to each executor."""
        return str(memory) + 'g'

    def _get_cores(self, cores: int = 18) -> str:
        """Returns the number of cores available to executors."""
        return str(cores)


# ------------------------------------------------------------------------------------------------ #
#                                        SPARK                                                     #
# ------------------------------------------------------------------------------------------------ #
class SparkCSV(IO):
    """IO using the Spark API"""


    def read(self, filepath: str, memory: int = 80, cores: int = 18, **kwargs) -> pyspark.sql.DataFrame:
        """Reads a Spark DataFrame from Parquet file resource

        Args:
            filepath (str): The path to the parquet file resource
            memory (int): The gb of memory allocated to each executor. Defaults to 90Gb
            cores (int): The number of cores allocated to each executor. Defaults to 18 cores.            

        Returns:
            Spark DataFrame
        """
        # Format resource configuration 
        cores = self._get_cores(cores)
        memory = self._get_memory(memory)

        # Set resources available.
        conf = SparkConf().setAll([('spark.executor.memory', memory),('spark.executor.cores',cores)])
        
        # Create spark session
        spark = SparkSession.builder.config(conf=conf).appName("Read CSV").getOrCreate()
        
        # Read the data
        sdf = spark.read.csv(filepath, inferSchema=True, header=True, sep=",",)
        spark.stop()
        return sdf


    def write(self, data: pyspark.sql.DataFrame, filepath: str, header: bool = True, 
        partition_by: list = None, mode: str = "overwrite", **kwargs) -> None:
        """Writes Spark DataFrame to Parquet file resource

        Args:
            data (pyspark.sql.DataFrame): Spark DataFrame to write
            filepath (str): The path to the parquet file to be written
            partition_by (list): List of strings containing partition column names  
            mode (str): 'overwrite' or 'append'. Default is 'overwrite'.
        """

        data.write.option("header", header) \
                  .csv(filepath)
        return data


    def _get_memory(self, memory: int = 90) -> int:
        """Returns the number of gigabytes of memory to be allocated to each executor."""
        return str(memory) + 'g'

    def _get_cores(self, cores: int = 18) -> str:
        """Returns the number of cores available to executors."""
        return str(cores)


# ------------------------------------------------------------------------------------------------ #
#                                      SPARK S3                                                    #
# ------------------------------------------------------------------------------------------------ #


class SparkS3(IO):
    """Read/Write utility between Spark and AWS S3

    Source: https://towardsai.net/p/programming/pyspark-aws-s3-read-write-operations

    """

    def read(self, filepath: str, **kwargs) -> pyspark.sql.DataFrame:
        """Reads a csv file from Amazon S3 bucket via Spark and returns pandas DataFrame

        Args:
            filepath (str): The path to the resource within the bucket, i.e. path/to/file.csv
            kwargs (dict): Contains the key/value pair 'bucket': 'bucket_name'

        Returns:
            pandas DataFrame
        """

        bucket = kwargs.get("bucket", None)
        spark = self._create_spark_session()
        sdf = spark.read.csv(f"s3a://{bucket}/{filepath}", header=True, inferSchema=True)
        spark.stop()
        pdf = sdf.toPandas()
        return pdf

    def write(self, data: Any, filepath: str, **kwargs) -> None:
        """Writes a pandas DataFrame to Amazon S3 via SparkSession

        Args:
            data (pd.DataFrame): The pandas Dataframe to write
            filepath (str): The path to the resource within the bucket, i.e. path/to/file.csv
            kwargs (dict): Contains the key/value pair 'bucket': 'bucket_name'
        """

        bucket = kwargs.get("bucket", None)
        # Convert pandas DataFrame to a Spark DataFrame object
        sdf = to_spark(data)
        sdf.write.format("csv").option("header", "true").save(
            f"s3a://{bucket}/{filepath}", mode="overwrite"
        )

    def _create_spark_session(self) -> pyspark.sql.SparkSession:

        # Set up Spark session on Spark Standalone Cluster
        os.environ["PYSPARK_SUBMIT_ARGS"] = (
            "-- packages com.amazonaws:aws-java-sdk:1.7.4,org."
            "apache.hadoop:hadoop-aws:2.7.3 pyspark-shell"
        )

        # Spark Configuration
        conf = (
            SparkConf()
            .set("spark.executor.extraJavaOptions", "-Dcom.amazonaws.services.s3.enableV4=true")
            .set("spark.driver.extraJavaOptions", "-Dcom.amazonaws.services.s3.enableV4=true")
            .setAppName("pyspark_aws")
            .setMaster("local[*]")
        )

        sc = SparkContext(conf=conf).getOrCreate()
        sc.setSystemProperty("com.amazonaws.services.s3.enableV4", "true")

        # Obtain credentials for Amazon S3
        load_dotenv()
        credentials_filepath = os.getenv("credentials_filepath")
        io = YamlIO()
        credentials = io.read(filepath=credentials_filepath)
        aws_credentials = credentials["cloud"].get("amazon")
        AWS_ACCESS_KEY_ID = aws_credentials.get("key")
        AWS_SECRET_ACCESS_KEY = aws_credentials.get("password")

        # Set Spark Hadoop properties for all worker nodes
        hadoopConf = sc._jsc.hadoopConfiguration()
        hadoopConf.set("fs.s3a.access.key", AWS_ACCESS_KEY_ID)
        hadoopConf.set("fs.s3a.secret.key", AWS_SECRET_ACCESS_KEY)
        hadoopConf.set("fs.s3a.endpoint", "s3-us-east-1.amazonaws.com")
        hadoopConf.set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")

        spark = SparkSession(sc)

        return spark


# ------------------------------------------------------------------------------------------------ #
class CsvIO(IO):
    """Handles IO of pandas DataFrames to /from CSV Files"""

    def read(
        self,
        filepath: str,
        sep: str = ",",
        header: list = None,
        names: list = None,
        usecols: list = None,
        index_col: bool = False,
        dtype: dict = None,
        n_chunks: int = 20,
        progress_bar: bool = True,
    ) -> pd.DataFrame:
        """Reads a CSV file into pandas DataFrame with progress monitor."""

        if progress_bar:
            return self._load_progress_bar(
                filepath=filepath,
                sep=sep,
                header=header,
                names=names,
                usecols=usecols,
                index_col=index_col,
                dtype=dtype,
                n_chunks=n_chunks,
            )
        else:
            return self._load_no_progress_bar(
                filepath=filepath,
                sep=sep,
                header=header,
                names=names,
                usecols=usecols,
                index_col=index_col,
                dtype=dtype,
                n_chunks=n_chunks,
            )

    def _load_progress_bar(
        self,
        filepath: str,
        sep: str = ",",
        header: list = None,
        names: list = None,
        usecols: list = None,
        index_col: bool = False,
        dtype: dict = None,
        n_chunks: int = 20,
    ) -> pd.DataFrame:

        rows = sum(1 for _ in open(filepath, "r"))

        header = self._get_read_header(header)

        chunksize = int(rows / n_chunks)

        chunks = []

        with tqdm(total=rows, desc="\tRows read: ") as bar:
            for chunk in pd.read_csv(
                filepath,
                sep=sep,
                header=header,
                names=names,
                usecols=usecols,
                index_col=index_col,
                dtype=dtype,
                low_memory=False,
                chunksize=chunksize,
            ):
                chunks.append(chunk)
                bar.update(len(chunk))

        df = pd.concat((f for f in chunks), axis=0)

        return df

    def _load_no_progress_bar(
        self,
        filepath: str,
        sep: str = ",",
        header: list = None,
        names: list = None,
        usecols: list = None,
        index_col: bool = False,
        dtype: dict = None,
        n_chunks: int = 20,
    ) -> pd.DataFrame:

        rows = sum(1 for _ in open(filepath, "r"))

        header = self._get_read_header(header)

        chunksize = int(rows / n_chunks)

        chunks = []

        for chunk in pd.read_csv(
            filepath,
            sep=sep,
            header=header,
            names=names,
            usecols=usecols,
            index_col=index_col,
            dtype=dtype,
            low_memory=False,
            chunksize=chunksize,
        ):
            chunks.append(chunk)

        df = pd.concat((f for f in chunks), axis=0)

        return df

    def write(
        self,
        data: pd.DataFrame,
        filepath: str,
        index_label: str = None,
        sep: str = ",",
        header: bool = True,
        index: bool = False,
        n_chunks: int = 20,
    ) -> None:
        """Writes a large DataFrame to CSV file with progress monitor."""

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        chunks = np.array_split(data.index, n_chunks)

        for chunk, subset in enumerate(tqdm(chunks)):
            if chunk == 0:  # Write in 'w' mode
                data.loc[subset].to_csv(
                    filepath,
                    sep=sep,
                    header=header,
                    index_label=index_label,
                    mode="w",
                    index=index,
                )
            else:
                data.loc[subset].to_csv(
                    filepath,
                    sep=sep,
                    index_label=index_label,
                    header=None,
                    mode="a",
                    index=index,
                )

    def _get_read_header(self, header: Any) -> Any:
        """Ensures that the header value for read_csv is 0 or None"""
        converter = {True: 0, False: None}
        if isinstance(header, bool):
            header = converter[header]
        return header


# ------------------------------------------------------------------------------------------------ #
class YamlIO(IO):
    """Reads and writes from and to Yaml files."""

    def read(self, filepath: str, **kwargs) -> dict:
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                return yaml.load(f, Loader=yamlordereddictloader.Loader)
        else:
            return {}

    def write(self, data: dict, filepath: str, **kwargs) -> None:
        with open(filepath, "r") as f:
            yaml.dump(data, f)
