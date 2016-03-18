# -*- coding: utf-8 -*-
import os
from client.newt import NewtClient


class SpotClient(NewtClient):
    """
    Client class to handle SPOT API calls
    """

    BASE_DIR = '/global/project/projectdirs/als/spade/warehouse'
    SPOT_URL = 'https://portal-auth.nersc.gov/als'

    def __init__(self, username, password, system=None):
        super(SpotClient, self).__init__(username, password, system)
        self.spot_authentication = None

    def login(self):
        credentials = {"username": str(self.username),
                       "password": str(self.password)}
        response = self.post(self.SPOT_URL + '/auth', data=credentials)
        if response.json()['auth']:
            self.authentication = response
            super(SpotClient, self).login()
        else:
            self.authentication = None

    def search(self, query, **kwargs):
        """
        Search a dataset on SPOT

        :param kwargs: str, optional, from
            'sortterm': attribute to sort results by
            'sorttype': ascending 'asc' or descending 'desc'
            'end_station': endstation of dataset
            'limitnum': maximum number of results to show
            'skipnum': number of results to skip
            'search': search query
        :return: json response of search results
        """
        self.check_login()
        # sortterm probably allows more filters will need to check...
        allowed_kwargs = {'sortterm': ['fs.stage_date', 'appmetadata.sdate'],
                          'sorttype': ['desc', 'asc'],
                          'end_station': ['bl832', 'bl733']}
        generic_kwargs = ['limitnum', 'skipnum']
        for key in kwargs:
            if key not in allowed_kwargs.keys() and key not in generic_kwargs:
                raise ValueError('%s keyword not in allowed keywords %s' %
                                 (key, list(allowed_kwargs.keys() +
                                  generic_kwargs)))
            elif key in allowed_kwargs:
                if kwargs[key] not in allowed_kwargs[key]:
                    raise ValueError('%s keyword value must be on of %s' %
                                     (kwargs[key], list(allowed_kwargs[key])))
        kwargs.update(search=query)

        r = self.get(self.SPOT_URL + '/hdf/search', params=kwargs)

        return self.check_response(r)

    def get_derived_datasets(self, dataset):
        """
        Get datasets that are derived from the given dataset. ie raw, sino,
        norm, etc...
        :param dataset: str, dataset name
        :return: json response with derived datasets
        """
        self.check_login()
        params = {'dataset': dataset}
        r = self.post(self.SPOT_URL + '/hdf/dataset', params=params)
        return self.check_response(r)

    def get_stage_path(self, dataset, stage):
        """
        Get the database path for a specific stage of a dataset. Stages
        are raw, norm, sino, gridrec, etc...

        :param dataset: str, name of dataset
        :param stage: str, stage name
        :return: str, database path
        """
        self.check_login()
        derivatives = self.get_derived_datasets(dataset)

        for i in range(len(derivatives)):
            if derivatives[i]['stage'] == stage:
                path = derivatives[i]['path']
                return path

        raise SPOTError('Stage %s in dataset %s does not exist' %
                        (stage, dataset))

    def get_file_location(self, dataset, stage):
        """
        Get the full location (system path) for a specific stage of a dataset.
        stages are raw, norm, sino, gridrec, etc...

        :param dataset: str, name of dataset
        :param stage: str, stage name
        :return: str, file path
        """
        self.check_login()
        derivatives = self.get_derived_datasets(dataset)

        for i in range(len(derivatives)):
            if derivatives[i]['stage'] == stage:
                location = derivatives[i]['phyloc']
                return location

        raise SPOTError('Stage %s in dataset %s does not exist' %
                        (stage, dataset))

    def get_dataset_attributes(self, dataset, stage='raw', group='/'):
        """
        Get hdf5 attributes of a specified dataset. group can be a specified
        image within the hdf5 file, or default '/' for top level attributes

        :param dataset:
        :param stage:
        :param group:
        :return: json reponse of attributes
        """
        path = self.get_stage_path(dataset, stage)
        params = {'group': group}
        r = self.post(self.SPOT_URL + '/hdf/attributes' + path, params=params)

        return self.check_response(r)

    def list_dataset_images(self, dataset, stage):
        """
        List images inside a given dataset

        :param dataset: str, dataset name
        :param stage: str, stage name
        :return: json response of image list
        """
        path = self.get_stage_path(dataset, stage)
        r = self.post(self.SPOT_URL + '/hdf/listimages' + path)

        return self.check_response(r)

    def get_dataset_size(self, dataset, stage):
        """
        Get the file size of a specified dataset

        :param dataset: str, dataset name
        :param stage: str, stage name
        :return: int, dataset size in bytes?
        """
        path = self.get_stage_path(dataset, stage)
        r = self.session.head(self.SPOT_URL + '/hdf/download' + path)
        head = r.headers
        size = int(head['content-length'])

        return size

    def download_raw_image(self, dataset, stage, image, fpath):
        """NOT IMPLEMENTED YET"""
        # TODO Implement this
        return

    def stage_tape_2_disk(self, dataset, stage):
        """
        Stage a dataset from tape to disk if needed

        :param dataset: str, dataset name
        :param stage: str, stage name
        :return:
        """
        path = self.get_stage_path(dataset, stage)
        r = self.post(self.SPOT_URL + '/hdf/stageifneeded' + path)

        return self.check_response(r)

    def download_dataset(self, dataset, stage, fpath, fname=None):
        """
        Download a specified dataset

        :param dataset: str, dataset name
        :param stage: str, stage name
        :param fname: str, optional, file name (default will be name on SPOT)
        :param fpath: str, path to location where file will be written
        :return: None
        """
        path = self.get_stage_path(dataset, stage)
        if fname is None:
            fname = path.split('/')[-1]
        file_name = os.path.join(fpath, fname)

        r = self.stage_tape_2_disk(dataset, stage)
        r = self.get(self.SPOT_URL + '/hdf/download' + path, stream=True)

        with open(file_name, 'wb') as f:
            for chunk in r.iter_content(chunk_size=64*1024):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
        r.close()

        return self.check_login(r)

    def download_dataset_generator(self, dataset, stage, fpath, fname=None,
                                   chunk_size=64*1024):
        """
        Download a dataset as a generator (yields the fraction downloaded)
        Useful to know the status of a download (for gui purposes)

        :param dataset: str, dataset name
        :param stage: str, stage name
        :param fpath: str, path to location where file will be written
        :param fname: str, optional, file name (default will be name on SPOT)
        :param chunk_size
        :return: None
        """
        path = self.get_stage_path(dataset, stage)
        if fname is None:
            fname = path.split('/')[-1]
        file_name = os.path.join(fpath, fname)
        file_size = float(self.get_dataset_size(dataset, stage))

        r = self.stage_tape_2_disk(dataset, stage)
        r = self.get(self.SPOT_URL + '/hdf/download' + path, stream=True)

        with open(file_name, 'wb') as f:
            downloaded = 0.0
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:  # filter out keep-alive new chunks
                    f.write(chunk)
                    f.flush()
                    downloaded += len(chunk)/file_size
                    yield downloaded
        r.close()

        return


class SPOTError(Exception):
    """Raised when SPOT gets angry"""
    pass