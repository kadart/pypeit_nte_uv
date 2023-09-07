"""
Module for NOT NTE

Started by copying VLT/XSHOOTER, so watch out for inherited stuff
Also copying quite a lot from the not_alfosc.py file.
In particular can remove ESO type things

.. include:: ../include/links.rst
"""
import numpy as np

from astropy.coordinates import SkyCoord
from astropy import units
from astropy.time import Time

from pypeit import msgs
from pypeit import telescopes
from pypeit import io
from pypeit.core import parse
from pypeit.core import framematch
from pypeit.spectrographs import spectrograph
from pypeit.images import detector_container
from pypeit.core import parse
from pypeit import data

from IPython import embed

class NOTNTESpectrograph(spectrograph.Spectrograph):
    """
    Child to handle NOT/NTE specific code
    Note that, like for Xshooter, we have 3 seperate classes for the arms
    """
    ndet = 1 # number of detectors
    name = 'not_nte'
    telescope = telescopes.NOTTelescopePar() # already have NOTTelescopePar from ALFOSC dev
    pypeline = 'Echelle'
    url = 'https://nte.nbi.ku.dk/'
    ech_fixed_format = True
    header_name = 'NTE'

    def init_meta(self):
        """
        Define how metadata are derived from the spectrograph files.

        That is, this associates the ``PypeIt``-specific metadata keywords
        with the instrument-specific header cards using :attr:`meta`.
        """
        self.meta = {}
        # Required (core)
        # Have used the options from not_alfosc, should be consistent
        # Dithering stuff from keck_nires
        self.meta['ra'] = dict(ext=0, card="RA")
        self.meta['dec'] = dict(ext=0, card='DEC')
        self.meta['target'] = dict(ext=0, card='OBJECT')
        self.meta['binning'] = dict(card=None, compound=True) # uses NOT style keys, see compound_meta
        self.meta['mjd'] = dict(ext=0, card=None, compound=True) # uses NOT style keys, see compound_meta
        self.meta['exptime'] = dict(ext=0, card='EXPTIME')
        self.meta['airmass'] = dict(ext=0, card='AIRMASS')
        self.meta['decker'] = dict(ext=0, card='SLIT') # This is maybe not the best choice, but the decker header is needed

        # Extras for config and frametyping
        self.meta['dispname'] = dict(ext=0, card='MODES')
        self.meta['idname'] = dict(ext=0, card='IMAGETYP')
        self.meta['arm'] = dict(ext=0, card="ARM")
        self.meta['instrument'] = dict(ext=0, card='INSTRUME')

        # Dithering
        # Need to edit this for NIR
##        self.meta['dithpat'] = dict(ext=0, card='DPATNAME')
##        self.meta['dithpos'] = dict(card=None, compound=True)
##        self.meta['dithoff'] = dict(ext=0, card='YOFFSET')


    def compound_meta(self, headarr, meta_key):
        """
        Methods to generate metadata requiring interpretation of the header
        data, instead of simply reading the value of a header card.

        Args:
            headarr (:obj:`list`):
                List of `astropy.io.fits.Header`_ objects.
            meta_key (:obj:`str`):
                Metadata keyword to construct.

        Returns:
            object: Metadata value read from the header(s).
        """
        # This comes from not_alfosc
        if meta_key == 'binning':
            # PypeIt frame
            binspatial = headarr[0]['DETXBIN']
            binspec = headarr[0]['DETYBIN']
            return parse.binning2string(binspec, binspatial)
        elif meta_key == 'mjd':
            time = headarr[0]['DATE-AVG']
            ttime = Time(time, format='isot')
            return ttime.mjd
        #elif meta_key == 'ra':
        #    objra = headarr[0]['OBJRA'] # Given in hours, not deg
        #    return objra*15.
        else :
            msgs.error("Not ready for this compound meta")

    def configuration_keys(self):
        """
        Return the metadata keys that define a unique instrument
        configuration.

        This list is used by :class:`~pypeit.metadata.PypeItMetaData` to
        identify the unique configurations among the list of frames read
        for a given reduction.

        Returns:
            :obj:`list`: List of keywords of data pulled from file headers
            and used to constuct the :class:`~pypeit.metadata.PypeItMetaData`
            object.
        """
        # Makes sense to use arm here
        # later should have more?
        return ['arm',"decker"]

    def pypeit_file_keys(self):
        """
        Define the list of keys to be output into a standard ``PypeIt`` file.

        Returns:
            :obj:`list`: The list of keywords in the relevant
            :class:`~pypeit.metadata.PypeItMetaData` instance to print to the
            :ref:`pypeit_file`.
        """
        # Not sure about this one
        return super().pypeit_file_keys() + ['dither']

    def check_frame_type(self, ftype, fitstbl, exprng=None):
        """
        Check for frames of the provided type.

        Args:
            ftype (:obj:`str`):
                Type of frame to check. Must be a valid frame type; see
                frame-type :ref:`frame_type_defs`.
            fitstbl (`astropy.table.Table`_):
                The table with the metadata for one or more frames to check.
            exprng (:obj:`list`, optional):
                Range in the allowed exposure time for a frame of type
                ``ftype``. See
                :func:`pypeit.core.framematch.check_frame_exptime`.

        Returns:
            `numpy.ndarray`_: Boolean array with the flags selecting the
            exposures in ``fitstbl`` that are ``ftype`` type frames.
        """
        good_exp = framematch.check_frame_exptime(fitstbl['exptime'], exprng)

        # Copying not_alfosc, might need to add more
        # Also using the header decisions made in Lise's python script
        # etalon? NIR? 
        # Might need to include telluric and/or sky in the science classified ftype

        if ftype == 'science':
            return good_exp & (fitstbl['idname'] == 'OBJECT') #| (fitstbl['target'] == 'STD,TELLURIC')  | (fitstbl['target'] == 'STD,SKY'))
        if ftype == 'standard':
            return good_exp & ((fitstbl['idname'] == 'STD') | (fitstbl['target'] == 'STD') | (fitstbl['target'] == 'STD,SLIT'))
        if ftype == 'bias':
            return good_exp & (fitstbl['idname'] == 'BIAS')
        if ftype in ['pixelflat', 'trace', 'illumflat']:
            return good_exp & ((fitstbl['idname'] == 'LAMP,FLAT') | (fitstbl['target'] == 'LAMP,TRACE'))
        if ftype == 'dark':
            return good_exp & (fitstbl['idname'] == 'DARK')
        if ftype in ['arc', 'tilt']:
            return good_exp & (fitstbl['idname'] == 'LAMP,WAVE')
        if ftype == 'pinhole':
            return good_exp & (fitstbl['idname'] == 'LAMP,TRACE')
        if ftype == "sky":
            return good_exp & (fitstbl['idname'] == 'SKY')

        msgs.warn('Cannot determine if frames are of type {0}.'.format(ftype))
        return np.zeros(len(fitstbl), dtype=bool)

class NOTNTEVISSpectrograph(NOTNTESpectrograph):
    """
    Child to handle NOT/NTE specific code
    """

    name = 'not_nte_vis'
    camera = 'nte_vis'
    supported = False
    comment = 'See :doc:`nte`'

    def get_detector_par(self, det, hdu=None):
        """
        Return metadata for the selected detector.

        Args:
            det (:obj:`int`):
                1-indexed detector number.
            hdu (`astropy.io.fits.HDUList`_, optional):
                The open fits file with the raw image of interest.  If not
                provided, frame-dependent parameters are set to a default.

        Returns:
            :class:`~pypeit.images.detector_container.DetectorContainer`:
            Object with the detector metadata.
        """
        # Binning
        binning = '1,1' if hdu is None else self.get_meta_value(self.get_headarr(hdu), 'binning')

        # Detector 1 (this all needs checking for a final version)
        detector_dict = dict(
            binning         = binning,
            det              =1,
            dataext         = 0,
            specaxis        = 1, #check this, opposite of xshooter?
            specflip        = False, # check this
            spatflip        = False, # check this
            platescale      = 0.23, # taken from NTE_NOT 2022 presentation slides
            darkcurr        = 0.0,
            saturation      = 65535., # check
            nonlinear       = 0.86, # check
            mincounts       = -1e10,
            numamplifiers   = 1,
            gain            = np.atleast_1d(0.595), # Get this value
            ronoise         = np.atleast_1d(3.0), # Get this value
            datasec=np.atleast_1d('[{}:{},:]'.format(1,1024)),  # Just trying something here
            oscansec= None ,  # Overscan not actually required
        )

        return detector_container.DetectorContainer(**detector_dict)

    @classmethod
    def default_pypeit_par(cls):
        """
        Return the default parameters to use for this instrument.

        Returns:
            :class:`~pypeit.par.pypeitpar.PypeItPar`: Parameters required by
            all of ``PypeIt`` methods.
        """
        par = super().default_pypeit_par()

        # Adjustments to parameters for VIS
        #turn_on = dict(use_biasimage=True, use_overscan=False, overscan_method='median',
        #               use_darkimage=False, use_illumflat=False, use_pixelflat=False,
        #               use_specillum=False)
        turn_off = dict(use_overscan=False)
        par.reset_all_processimages_par(**turn_off)

        # The below is sufficient for OK edge tracing, probably not a necessary set
        par['calibrations']['slitedges']['edge_thresh'] = 5.0
        par['calibrations']['slitedges']['fit_order'] = 5
        par['calibrations']['slitedges']['max_shift_adj'] = 0.5
        par['calibrations']['slitedges']['trace_thresh'] = 10
        par['calibrations']['slitedges']['fit_min_spec_length'] = 0.1
        par['calibrations']['slitedges']['length_range'] = 0.3

        par['calibrations']['slitedges']['det_buffer'] = 1
        par['calibrations']['slitedges']['max_nudge'] = 1
        #par['calibrations']['slitedges']['left_right_pca'] = False
        #par['calibrations']['slitedges']['add_slits'] = "1:2280:35:124"
        #par['calibrations']['slitedges']['sync_predict'] = "nearest"
        par['calibrations']['slitedges']['smash_range'] = [0.3,0.7]
        #par['calibrations']['slitedges']['sobel_mode'] = "constant"


        # Start on wl calib
        par['calibrations']['wavelengths']['lamps'] = ["HgAr_NTE_VIS"]
        par['calibrations']['wavelengths']['rms_threshold'] = 0.4
        par['calibrations']['wavelengths']['sigdetect'] = 2.0
        par['calibrations']['wavelengths']['fwhm'] = 4.0
        par['calibrations']['wavelengths']['n_final'] = 4# [2, 4, 4, 4, 4, 4, 4, 4]
        par['calibrations']['wavelengths']['nreid_min'] = 1 # important
        
        par['calibrations']['wavelengths']['reference'] = 'arc'
        par['calibrations']['wavelengths']['reid_arxiv'] = 'not_nte_vis.fits'
        par['calibrations']['wavelengths']['method'] = 'full_template'
        par['calibrations']['wavelengths']['nsnippet'] = 1 # important

        # Echelle parameters
        par['calibrations']['wavelengths']['echelle'] = True
        par['calibrations']['wavelengths']['ech_nspec_coeff'] = 5
        par['calibrations']['wavelengths']['ech_norder_coeff'] = 5
        par['calibrations']['wavelengths']['ech_sigrej'] = 3.0

        # tilts
        #par['calibrations']['tilts']['spat_order'] =  3
        
        # Flat
        par['calibrations']['flatfield']['slit_illum_finecorr'] = False # turn off for now

        # skysub
        par['reduce']['skysub']['bspline_spacing'] = 1

        # extraction
        par['reduce']['findobj']['maxnumber_sci'] = 1
        par['reduce']['findobj']['maxnumber_std'] = 1


        # Sensitivity function parameters
        par['sensfunc']['algorithm'] = 'IR'
        #par['sensfunc']['polyorder'] = [9, 11, 11, 9, 9, 8, 8, 7, 7, 7, 7, 7, 7, 7, 7]
        #par['sensfunc']['IR']['telgridfile'] = 'TelFit_Paranal_VIS_4900_11100_R25000.fits'

        return par

    @property
    def norders(self):
        """
        Number of orders observed for this spectograph.
        """
        return 8

    @property
    def order_spat_pos(self):
        """
        Return the expected spatial position of each echelle order.
        """

        return np.array([0.17285156, 0.31542969, 0.43554688, 0.54980469,
                         0.64941406,0.75195312, 0.84960938, 0.9375])


        #np.array([73, 207, 332, 449, 558, 660 ,757,854]) were the positions used
        #np.array([177, 323, 446, 563, 665, 770 ,870,960]) are the new positions used

        # normalised by the detector height

    @property
    def orders(self):
        """
        Return the order number for each echelle order.
        """
        return np.arange(15, 7, -1, dtype=int) # orders 15-8, from NTE_NOT_2022 slides

    @property
    def spec_min_max(self):
        """
        Return the minimum and maximum spectral pixel expected for the
        spectral range of each order.
        """
        spec_min = np.asarray([0]*8)
        spec_max = np.asarray([2000,3000,4000,4000,4000,4000,4000,4000])
        return np.vstack((spec_min, spec_max))


    def order_platescale(self, order_vec, binning=None):
        """
        Return the platescale for each echelle order.

        This routine is only defined for echelle spectrographs, and it is
        undefined in the base class.

        Args:
            order_vec (`numpy.ndarray`_):
                The vector providing the order numbers.
            binning (:obj:`str`, optional):
                The string defining the spectral and spatial binning.

        Returns:
            `numpy.ndarray`_: An array with the platescale for each order
            provided by ``order``.
        """
        # VIS has no binning, but for an instrument with binning we would do this
        binspectral, binspatial = parse.parse_binning(binning)

        # ToDO Work this out
        
        # Right now I just assume constant
        plate_scale = np.ones(8) * 0.23 
        return plate_scale*binspatial

        # Not sure about this, commenting out
##    @property
##    def dloglam(self):
##        """
##        Return the logarithmic step in wavelength for output spectra.
##        """
##        # This number was computed by taking the mean of the dloglam for all
##        # the X-shooter orders. The specific loglam across the orders deviates
##        # from this value by +-7% from this first to final order. This is the
##        # unbinned value. It was actually measured to be 1.69207e-5 from a 2x1
##        # data and then divided by two.
##        return 8.46035e-06

    @property
    def loglam_minmax(self):
        """
        Return the base-10 logarithm of the first and last wavelength for
        ouput spectra.
        """
        return np.log10(4200), np.log10(9150)

    def bpm(self, filename, det, shape=None, msbias=None):
        """
        Generate a default bad-pixel mask.

        Even though they are both optional, either the precise shape for
        the image (``shape``) or an example file that can be read to get
        the shape (``filename`` using :func:`get_image_shape`) *must* be
        provided.

        Args:
            filename (:obj:`str` or None):
                An example file to use to get the image shape.
            det (:obj:`int`):
                1-indexed detector number to use when getting the image
                shape from the example file.
            shape (tuple, optional):
                Processed image shape
                Required if filename is None
                Ignored if filename is not None
            msbias (`numpy.ndarray`_, optional):
                Master bias frame used to identify bad pixels

        Returns:
            `numpy.ndarray`_: An integer array with a masked value set
            to 1 and an unmasked value set to 0.  All values are set to
            0.
        """
        # Call the base-class method to generate the empty bpm

        # THE BELOW MASKS OUT THE +/- 1 ORDERS, NOT A REAL BPM AND MAY NOT BE IN THE FINAL CODE
        
        bpm_img = super().bpm(filename, det, shape=shape, msbias=msbias)
        bpm_dir = data.Paths.static_calibs / 'not_nte'
        bpm_loc = np.loadtxt(bpm_dir / 'mask_VIS.dat', usecols=(0,1))
        
        for i in range(0,4096):
            bpm_img[i] = np.append(np.ones(int(bpm_loc[i][0])),np.zeros(int(1024-bpm_loc[i][0])))

        
        return bpm_img


class NOTNTENIRSpectrograph(NOTNTESpectrograph):
    """
    Child to handle NTE/NIR specific code
    """

    name = 'not_nte_nir'
    camera = 'nte_nir'
    supported = False
    comment = 'See :doc:`nte`'

    def get_detector_par(self, det, hdu=None):
        """
        Return metadata for the selected detector.

        Args:
            det (:obj:`int`):
                1-indexed detector number.
            hdu (`astropy.io.fits.HDUList`_, optional):
                The open fits file with the raw image of interest.  If not
                provided, frame-dependent parameters are set to a default.

        Returns:
            :class:`~pypeit.images.detector_container.DetectorContainer`:
            Object with the detector metadata.
        """
        # Detector 1
        detector_dict = dict(
            binning         = '1,1',  # No binning in near-IR
            det             = 1,
            dataext         = 0,
            specaxis        = 1,
            specflip        = False,
            spatflip        = False,
            platescale      = 0.46, # taken from NTE_NOT 2022 presentation slides, requires checking
            darkcurr        = 0.0, # CHECK
            saturation      = 2.0e5, # CHECK, although saturation should never be a problem in IR if you are observing properly
            nonlinear       = 0.86, # CHECK,
            mincounts       = -1e10, 
            numamplifiers   = 1,
            gain            = np.atleast_1d(2.16), # e/ADU, from the MPIA test report
            ronoise         = np.atleast_1d(10.6), # e-, from the MPIA test report
            datasec=np.atleast_1d('[{}:{},:]'.format(1,2048)),  # Just trying something here
            #datasec         = np.atleast_1d('[4:2044,4:]'), # These are all unbinned pixels
            oscansec= None , # Should check if we want an overscan
            )
        return detector_container.DetectorContainer(**detector_dict)

    @classmethod
    def default_pypeit_par(cls):
        """
        Return the default parameters to use for this instrument.

        Returns:
            :class:`~pypeit.par.pypeitpar.PypeItPar`: Parameters required by
            all of ``PypeIt`` methods.
        """

        par = super().default_pypeit_par()
        # Turn off illumflat, bias, oversscan and dark (?)
        turn_off = dict(use_illumflat=False, use_biasimage=False, use_overscan=False,
                        use_darkimage=False)
        par.reset_all_processimages_par(**turn_off)


# The below is all the X-shooter settings

##        par = super().default_pypeit_par()        
##
##        # Turn off illumflat
##        turn_off = dict(use_illumflat=False, use_biasimage=False, use_overscan=False,
##                        use_darkimage=False)
##        par.reset_all_processimages_par(**turn_off)
##        # Require dark images to be subtracted from the flat images used for
##        # tracing, pixelflats, and illumflats
##        # par['calibrations']['traceframe']['process']['use_darkimage'] = True
##        # par['calibrations']['pixelflatframe']['process']['use_darkimage'] = True
##        # par['calibrations']['illumflatframe']['process']['use_darkimage'] = True
##        # TODO: `mask_cr` now defaults to True for darks.  Should this be turned off?
##
##        # Is this needed below?
##        par['scienceframe']['process']['sigclip'] = 20.0
##        par['scienceframe']['process']['satpix'] = 'nothing'
##        # TODO tune up LA COSMICS parameters here for X-shooter as tellurics are being excessively masked
##
##
##        # Adjustments to slit and tilts for NIR
##        par['calibrations']['slitedges']['edge_thresh'] = 50.
##        par['calibrations']['slitedges']['fit_order'] = 8
##        par['calibrations']['slitedges']['max_shift_adj'] = 0.5
##        par['calibrations']['slitedges']['trace_thresh'] = 10.
##        par['calibrations']['slitedges']['fit_min_spec_length'] = 0.5
##        par['calibrations']['slitedges']['left_right_pca'] = True
##        par['calibrations']['slitedges']['length_range'] = 0.3
##
##        # Tilt parameters
##        par['calibrations']['tilts']['rm_continuum'] = True
##        par['calibrations']['tilts']['tracethresh'] =  25.0
##        par['calibrations']['tilts']['maxdev_tracefit'] =  0.04
##        par['calibrations']['tilts']['maxdev2d'] =  0.04
##        par['calibrations']['tilts']['spat_order'] =  3
##        par['calibrations']['tilts']['spec_order'] =  4
##
##        # 1D wavelength solution
##        par['calibrations']['wavelengths']['lamps'] = ['OH_XSHOOTER']
##        par['calibrations']['wavelengths']['rms_threshold'] = 0.25
##        par['calibrations']['wavelengths']['sigdetect'] = 10.0
##        par['calibrations']['wavelengths']['fwhm'] = 5.0
##        par['calibrations']['wavelengths']['n_final'] = 4
##        # Reidentification parameters
##        par['calibrations']['wavelengths']['method'] = 'reidentify'
##        par['calibrations']['wavelengths']['reid_arxiv'] = 'vlt_xshooter_nir.fits'
##        par['calibrations']['wavelengths']['cc_thresh'] = 0.50
##        par['calibrations']['wavelengths']['cc_local_thresh'] = 0.50
###        par['calibrations']['wavelengths']['ech_fix_format'] = True
##        # Echelle parameters
##        par['calibrations']['wavelengths']['echelle'] = True
##        par['calibrations']['wavelengths']['ech_nspec_coeff'] = 5
##        par['calibrations']['wavelengths']['ech_norder_coeff'] = 5
##        par['calibrations']['wavelengths']['ech_sigrej'] = 3.0
##
##        # Flats
##        #par['calibrations']['standardframe']['process']['illumflatten'] = False
##        par['calibrations']['flatfield']['tweak_slits_thresh'] = 0.90
##        par['calibrations']['flatfield']['tweak_slits_maxfrac'] = 0.10
##
##        # Standards
##        par['calibrations']['standardframe']['process']['mask_cr'] = False
##
##        # Extraction
##        par['reduce']['skysub']['bspline_spacing'] = 0.8
##        par['reduce']['skysub']['global_sky_std']  = False # Do not perform global sky subtraction for standard stars
##        par['reduce']['extraction']['model_full_slit'] = True  # local sky subtraction operates on entire slit
##        par['reduce']['findobj']['trace_npoly'] = 8
##        par['reduce']['findobj']['maxnumber_sci'] = 2  # Assume that there is only one object on the slit.
##        par['reduce']['findobj']['maxnumber_std'] = 1  # Assume that there is only one object on the slit.
##
##
##        # The settings below enable X-shooter dark subtraction from the traceframe and pixelflatframe, but enforce
##        # that this bias won't be subtracted from other images. It is a hack for now, because eventually we want to
##        # perform this operation with the dark frame class, and we want to attach individual sets of darks to specific
##        # images.
##        #par['calibrations']['biasframe']['useframe'] = 'bias'
##        #par['calibrations']['traceframe']['process']['bias'] = 'force'
##        #par['calibrations']['pixelflatframe']['process']['bias'] = 'force'
##        #par['calibrations']['arcframe']['process']['bias'] = 'skip'
##        #par['calibrations']['tiltframe']['process']['bias'] = 'skip'
##        #par['calibrations']['standardframe']['process']['bias'] = 'skip'
##        #par['scienceframe']['process']['bias'] = 'skip'
##
##        # Sensitivity function parameters
##        par['sensfunc']['algorithm'] = 'IR'
##        par['sensfunc']['polyorder'] = 8
##        par['sensfunc']['IR']['telgridfile'] = 'TelFit_Paranal_NIR_9800_25000_R25000.fits'
##
##        return par


    def init_meta(self):
        """
        Define how metadata are derived from the spectrograph files.

        That is, this associates the ``PypeIt``-specific metadata keywords
        with the instrument-specific header cards using :attr:`meta`.
        """
        super().init_meta()
        # No binning in the NIR (true also for nte?)
        self.meta['binning'] = dict(card=None, default='1,1')

        # Required
        #self.meta['decker'] = dict(ext=0, card='HIERARCH ESO INS OPTI5 NAME')

        # Dark-flat identification via exposure number
        #self.meta['seq_expno'] = dict(ext=0, card='HIERARCH ESO TPL EXPNO')

    def pypeit_file_keys(self):
        """
        Define the list of keys to be output into a standard ``PypeIt`` file.

        Returns:
            :obj:`list`: The list of keywords in the relevant
            :class:`~pypeit.metadata.PypeItMetaData` instance to print to the
            :ref:`pypeit_file`.
        """
        pypeit_keys = super().pypeit_file_keys()
        # TODO: Why are these added here? See
        # pypeit.metadata.PypeItMetaData.set_pypeit_cols
        pypeit_keys += ['calib', 'comb_id', 'bkg_id']
        return pypeit_keys


    # Use this if we need different frame type rules here than for VIS
##    def check_frame_type(self, ftype, fitstbl, exprng=None):
##        """
##        Check for frames of the provided type.
##
##        Args:
##            ftype (:obj:`str`):
##                Type of frame to check. Must be a valid frame type; see
##                frame-type :ref:`frame_type_defs`.
##            fitstbl (`astropy.table.Table`_):
##                The table with the metadata for one or more frames to check.
##            exprng (:obj:`list`, optional):
##                Range in the allowed exposure time for a frame of type
##                ``ftype``. See
##                :func:`pypeit.core.framematch.check_frame_exptime`.
##
##        Returns:
##            `numpy.ndarray`_: Boolean array with the flags selecting the
##            exposures in ``fitstbl`` that are ``ftype`` type frames.
##        """
##        good_exp = framematch.check_frame_exptime(fitstbl['exptime'], exprng)
##
##        # Default NIR calibration behavior is to take flat/darks in sequence
##        #  These are marked by the seq_expno column
##        good_flat_seq = np.array([seq is not None and int(seq) % 2 == 1 for seq in fitstbl['seq_expno']])
##        good_dark_seq = np.array([seq is not None and int(seq) % 2 == 0 for seq in fitstbl['seq_expno']])
##
##        # TODO: Allow for 'sky' frame type, for now include sky in
##        # 'science' category
##        if ftype == 'science':
##            return good_exp & ((fitstbl['idname'] == 'SCIENCE')
##                                | (fitstbl['target'] == 'STD,TELLURIC')
##                                | (fitstbl['target'] == 'STD,SKY'))
##        if ftype == 'standard':
##            return good_exp & (fitstbl['target'] == 'STD,FLUX')
##        if ftype == 'bias':
##            return good_exp & (fitstbl['target'] == 'BIAS')
##        if ftype == 'sky':
##            return good_exp & (fitstbl['target'] == 'DARK')
##
##        if ftype in ['pixelflat', 'trace']:
##            # Flats and trace frames are typed together
##            # Lamp on flats are taken first (odd exposure number)
##            return good_exp & (((fitstbl['target'] == 'LAMP,DFLAT')
##                               | (fitstbl['target'] == 'LAMP,QFLAT')
##                               | (fitstbl['target'] == 'LAMP,FLAT'))
##                               & good_flat_seq)
##
##        if ftype in ['dark']:
##            # Lamp off flats are taken second (even exposure number)
##            return good_exp & (((fitstbl['target'] == 'LAMP,DFLAT')
##                                | (fitstbl['target'] == 'LAMP,QFLAT')
##                                | (fitstbl['target'] == 'LAMP,FLAT'))
##                               & good_dark_seq)
##
##        if ftype == 'pinhole':
##            # Don't type pinhole
##            return np.zeros(len(fitstbl), dtype=bool)
##        if ftype in ['arc', 'tilt']:
##            return good_exp & ((fitstbl['target'] == 'LAMP,WAVE') | (fitstbl['target'] == 'SCIENCE'))
##
##        msgs.warn('Cannot determine if frames are of type {0}.'.format(ftype))
##        return np.zeros(len(fitstbl), dtype=bool)

    def bpm(self, filename, det, shape=None, msbias=None):
        """
        Generate a default bad-pixel mask.

        Even though they are both optional, either the precise shape for
        the image (``shape``) or an example file that can be read to get
        the shape (``filename`` using :func:`get_image_shape`) *must* be
        provided.

        Args:
            filename (:obj:`str` or None):
                An example file to use to get the image shape.
            det (:obj:`int`):
                1-indexed detector number to use when getting the image
                shape from the example file.
            shape (tuple, optional):
                Processed image shape
                Required if filename is None
                Ignored if filename is not None
            msbias (`numpy.ndarray`_, optional):
                Master bias frame used to identify bad pixels

        Returns:
            `numpy.ndarray`_: An integer array with a masked value set
            to 1 and an unmasked value set to 0.  All values are set to
            0.
        """
        # Call the base-class method to generate the empty bpm
        bpm_img = super().bpm(filename, det, shape=shape, msbias=msbias)
        # Should return an empty bpm
        return bpm_img


##        if det == 1:
##            bpm_dir = data.Paths.static_calibs / 'vlt_xshoooter'
##            try :
##                bpm_loc = np.loadtxt(bpm_dir / 'BP_MAP_RP_NIR.dat', usecols=(0,1))
##            except IOError :
##                msgs.warn('BP_MAP_RP_NIR.dat not present in the static database')
##                bpm_fits = io.fits_open(bpm_dir / 'BP_MAP_RP_NIR.fits.gz')
##                # ToDo: this depends on datasec, biassec, specflip, and specaxis
##                #       and should become able to adapt to these parameters.
##                # Flipping and shifting BPM to match the PypeIt format
##                y_shift = -2
##                x_shift = 18
##                bpm_data = np.flipud(bpm_fits[0].data)
##                y_len = len(bpm_data[:,0])
##                x_len = len(bpm_data[0,:])
##                bpm_data_pypeit = np.full( ((y_len+abs(y_shift)),(x_len+abs(x_shift))) , 0)
##                bpm_data_pypeit[:-abs(y_shift),:-abs(x_shift)] = bpm_data_pypeit[:-abs(y_shift),:-abs(x_shift)] + bpm_data
##                bpm_data_pypeit = np.roll(bpm_data_pypeit,-y_shift,axis=0)
##                bpm_data_pypeit = np.roll(bpm_data_pypeit,x_shift,axis=1)
##                filt_bpm = bpm_data_pypeit[1:y_len,1:x_len]>100.
##                y_bpm, x_bpm = np.where(filt_bpm)
##                bpm_loc = np.array([y_bpm,x_bpm]).T
##                np.savetxt(bpm_dir / 'BP_MAP_RP_NIR.dat', bpm_loc, fmt=['%d','%d'])
##            finally :
##                bpm_img[bpm_loc[:,0].astype(int),bpm_loc[:,1].astype(int)] = 1.
##
##        return bpm_img

    @property
    def norders(self):
        """
        Number of orders for this spectograph. Should only defined for
        echelle spectrographs, and it is undefined for the base class.
        """
        return 5

    @property
    def order_spat_pos(self):
        """
        Return the expected spatial position of each echelle order.
        """
        return np.array([0.13720703, 0.12792969, 0.22949219, 0.30761719, 0.45898438])
    
        # using 281,262,470,630,940 / 2048

    @property
    def orders(self):
        """
        Return the order number for each echelle order.
        """
        return np.arange(7, 2, -1, dtype=int) # orders 7-3, from NTE_NOT_2022 slides

    @property
    def spec_min_max(self):
        """
        Return the minimum and maximum spectral pixel expected for the
        spectral range of each order.
        """
        spec_max = np.asarray([2048]*5)
        spec_min = np.asarray([0]*5)
        return np.vstack((spec_min, spec_max))

    def order_platescale(self, order_vec, binning=None):
        """
        Return the platescale for each echelle order.

        This routine is only defined for echelle spectrographs, and it is
        undefined in the base class.

        Args:
            order_vec (`numpy.ndarray`_):
                The vector providing the order numbers.
            binning (:obj:`str`, optional):
                The string defining the spectral and spatial binning.

        Returns:
            `numpy.ndarray`_: An array with the platescale for each order
            provided by ``order``.
        """
        # TODO: Either assume a linear trend or measure this
        # Should work this out properly

        # Right now I just assume constant, this is not correct
        plate_scale = np.ones(5) * 0.46
        return plate_scale

        # Skip this for now
##    @property
##    def dloglam(self):
##        """
##        Return the logarithmic step in wavelength for output spectra.
##        """
##        # This number was computed by taking the mean of the dloglam for all
##        # the X-shooter orders. The specific loglam across the orders deviates
##        # from this value by +-6% from this first to final order
##        return 1.93724e-5

    @property
    def loglam_minmax(self):
        """
        Return the base-10 logarithm of the first and last wavelength for
        ouput spectra.
        """
        return np.log10(8500.0), np.log10(25000)

##class VLTXShooterUVBSpectrograph(VLTXShooterSpectrograph):
##    """
##    Child to handle VLT/XSHOOTER specific code for the UVB arm
##    """
##
##    name = 'vlt_xshooter_uvb'
##    camera = 'XShooter_UVB'
##    supported = True
##    comment = 'See :doc:`xshooter`'
##
##    def get_detector_par(self, det, hdu=None):
##        """
##        Return metadata for the selected detector.
##
##        Args:
##            det (:obj:`int`):
##                1-indexed detector number.
##            hdu (`astropy.io.fits.HDUList`_, optional):
##                The open fits file with the raw image of interest.  If not
##                provided, frame-dependent parameters are set to a default.
##
##        Returns:
##            :class:`~pypeit.images.detector_container.DetectorContainer`:
##            Object with the detector metadata.
##        """
##        # Binning
##        binning = '1,1' if hdu is None else self.get_meta_value(self.get_headarr(hdu), 'binning')
##
##        # Detector 1
##        detector_dict = dict(
##            binning         = binning,
##            det             = 1,
##            dataext         = 0,
##            specaxis        = 0,
##            specflip        = True,
##            spatflip        = True,
##            platescale      = 0.161, # average from order 14 and order 24, see manual
##            darkcurr        = 0.0,
##            saturation      = 65000.,
##            nonlinear       = 0.86,
##            mincounts       = -1e10,
##            numamplifiers   = 1,
##            gain            = np.atleast_1d(1.61),
##            ronoise         = np.atleast_1d(2.60),
##            datasec         = np.atleast_1d('[:,49:2096]'), # '[49:2000,1:2999]',
##            oscansec        = np.atleast_1d('[:,1:48]'), # '[1:48, 1:2999]',
##            )
##        # Return
##        return detector_container.DetectorContainer(**detector_dict)
##
##    @classmethod
##    def default_pypeit_par(cls):
##        """
##        Return the default parameters to use for this instrument.
##
##        Returns:
##            :class:`~pypeit.par.pypeitpar.PypeItPar`: Parameters required by
##            all of ``PypeIt`` methods.
##        """
##        par = super().default_pypeit_par()
##
##        # Adjustments to parameters for UVB (following VIS)
##        turn_on = dict(use_biasimage=False, use_overscan=True, overscan_method='median',
##                       use_darkimage=False, use_illumflat=False, use_pixelflat=False,
##                       use_specillum=False)
##        par.reset_all_processimages_par(**turn_on)
##
##        # X-SHOOTER arcs/tilts are also have different binning with bias
##        # frames, so don't use bias frames. Don't use the biases for any
##        # calibrations since it appears to be a different amplifier readout
##
##        # Adjustments to slit and tilts for UVB
##        par['calibrations']['slitedges']['edge_thresh'] = 8.
##        par['calibrations']['slitedges']['max_shift_adj'] = 0.5
##        par['calibrations']['slitedges']['trace_thresh'] = 10.
##        par['calibrations']['slitedges']['left_right_pca'] = True
##        par['calibrations']['slitedges']['length_range'] = 0.3
##
##        # 1D wavelength solution
##        par['calibrations']['wavelengths']['lamps'] = ['ThAr_XSHOOTER_UVB']
##        par['calibrations']['wavelengths']['n_final'] = [3] + 10*[4]
##        par['calibrations']['wavelengths']['rms_threshold'] = 0.60
##        par['calibrations']['wavelengths']['sigdetect'] = 3.0 # Pretty faint lines in places
##        # Reidentification parameters
##        par['calibrations']['wavelengths']['method'] = 'reidentify'
##        par['calibrations']['wavelengths']['reid_arxiv'] = 'vlt_xshooter_uvb1x1.fits'
###        par['calibrations']['wavelengths']['ech_fix_format'] = True
##        # Echelle parameters
##        par['calibrations']['wavelengths']['echelle'] = True
##        par['calibrations']['wavelengths']['ech_nspec_coeff'] = 4
##        par['calibrations']['wavelengths']['ech_norder_coeff'] = 4
##        par['calibrations']['wavelengths']['ech_sigrej'] = 3.0
##
##        par['calibrations']['wavelengths']['cc_thresh'] = 0.50
##        par['calibrations']['wavelengths']['cc_local_thresh'] = 0.50
##
##        # Right now we are using the overscan and not biases becuase the
##        # standards are read with a different read mode and we don't yet have
##        # the option to use different sets of biases for different standards,
##        # or use the overscan for standards but not for science frames
##        par['scienceframe']['process']['use_biasimage']=True
##        par['scienceframe']['process']['use_illumflat']=True
##        par['scienceframe']['process']['use_pixelflat']=True
##        par['calibrations']['standardframe']['process']['use_illumflat']=True
##        par['calibrations']['standardframe']['process']['use_pixelflat']=True
##
##
##        # Extraction
##        par['reduce']['skysub']['bspline_spacing'] = 0.5
##        par['reduce']['skysub']['global_sky_std'] = False
##        par['reduce']['extraction']['model_full_slit'] = True
##        # Mask 3 edges pixels since the slit is short, insted of default (5,5)
##        par['reduce']['findobj']['find_trim_edge'] = [3,3]
##        # Continnum order for determining thresholds
##        #par['reduce']['findobj']['find_npoly_cont'] = 0
##        # Don't attempt to fit a continuum to the trace rectified image
##        #par['reduce']['findobj']['find_cont_fit'] = False
##        par['reduce']['findobj']['maxnumber_sci'] = 2  # Assume that there is a max of 2 objects on the slit
##        par['reduce']['findobj']['maxnumber_std'] = 1  # Assume that there is only one object on the slit.
##
##        return par
##
##    def init_meta(self):
##        """
##        Define how metadata are derived from the spectrograph files.
##
##        That is, this associates the ``PypeIt``-specific metadata keywords
##        with the instrument-specific header cards using :attr:`meta`.
##        """
##        super().init_meta()
##        # Add the name of the dispersing element
##
##        # Required
##        self.meta['decker'] = dict(ext=0, card='HIERARCH ESO INS OPTI3 NAME')
##
##    @property
##    def norders(self):
##        """
##        Number of orders observed for this spectograph.
##        """
##        return 11
##
##    @property
##    def order_spat_pos(self):
##        """
##        Return the expected spatial position of each echelle order.
##
##        The following lines generated the values below:
##
##        .. code-block:: python
##
##            from pypeit import edgetrace
##            edges = edgetrace.EdgeTraceSet.from_file('MasterEdges_A_1_DET01.fits.gz')
##
##            nrm_edges = edges.edge_fit[edges.nspec//2,:] / edges.nspat
##            slit_cen = ((nrm_edges + np.roll(nrm_edges,1))/2)[np.arange(nrm_edges.size//2)*2+1]
##
##        """
##        # This starts by ignoring the first, partial order (25?)
##        #  Order 24 is very faint and not included here
##        #  Order 12 is very faint and not included here (the flat crashes out with issues..)
##        return np.array([0.32671887, 0.39553878, 0.45989826, 0.52009878, 0.5764598,
##            0.62917188, 0.67859507, 0.72482729, 0.76815531, 0.80879042,
##            0.84700373])#, 0.88317493])
##
##    @property
##    def orders(self):
##        """
##        Return the order number for each echelle order.
##        """
##        return np.arange(23, 12, -1, dtype=int)  # 11 orders; the reddest is too faint to use
##        #return np.arange(23, 11, -1, dtype=int)   # 12 orders
##
##    @property
##    def spec_min_max(self):
##        """
##        Return the minimum and maximum spectral pixel expected for the
##        spectral range of each order.
##        """
##        spec_max = np.asarray([4000]*13)# + [3000])
##        spec_min = np.asarray([0]*13)
##        return np.vstack((spec_min, spec_max))
##
##    def order_platescale(self, order_vec, binning = None):
##        """
##        Return the platescale for each echelle order.
##
##        This routine is only defined for echelle spectrographs, and it is
##        undefined in the base class.
##
##        Args:
##            order_vec (`numpy.ndarray`_):
##                The vector providing the order numbers.
##            binning (:obj:`str`, optional):
##                The string defining the spectral and spatial binning.
##
##        Returns:
##            `numpy.ndarray`_: An array with the platescale for each order
##            provided by ``order``.
##        """
##        binspectral, binspatial = parse.parse_binning(binning)
##
##        # ToDO Either assume a linear trend or measure this
##        # X-shooter manual says, but gives no exact numbers per order.
##        # UVB: 65.9 pixels (0.167“/pix) at order 14 to 70.8 pixels (0.155”/pix) at order 24
##
##        # Assume a simple linear trend
##        plate_scale = 0.155 + (order_vec - 24)*(0.155-0.167)/(24 - 14)
##
##        # Right now I just took the average
##        return np.full(self.norders, 0.161)*binspatial
##
##    def bpm(self, filename, det, shape=None, msbias=None):
##        """
##        Generate a default bad-pixel mask.
##
##        Even though they are both optional, either the precise shape for
##        the image (``shape``) or an example file that can be read to get
##        the shape (``filename`` using :func:`get_image_shape`) *must* be
##        provided.
##
##        Args:
##            filename (:obj:`str` or None):
##                An example file to use to get the image shape.
##            det (:obj:`int`):
##                1-indexed detector number to use when getting the image
##                shape from the example file.
##            shape (tuple, optional):
##                Processed image shape
##                Required if filename is None
##                Ignored if filename is not None
##            msbias (`numpy.ndarray`_, optional):
##                Master bias frame used to identify bad pixels
##
##        Returns:
##            `numpy.ndarray`_: An integer array with a masked value set
##            to 1 and an unmasked value set to 0.  All values are set to
##            0.
##        """
##        # Call the base-class method to generate the empty bpm
##        bpm_img = super().bpm(filename, det, shape=shape, msbias=msbias)
##
##        # TODO -- Mask bad column if it is problematic (it isn't so far)
##
##        return bpm_img

class NOTNTEUVSpectrograph(NOTNTESpectrograph):
    """
    Child to handle NOT/NTE specific code
    """

    name = 'not_nte_uv'
    camera = 'nte_uv'
    supported = False
    comment = 'See :doc:`nte`'

    def get_detector_par(self, det, hdu=None):
        """
        Return metadata for the selected detector.

        Args:
            det (:obj:`int`):
                1-indexed detector number.
            hdu (`astropy.io.fits.HDUList`_, optional):
                The open fits file with the raw image of interest.  If not
                provided, frame-dependent parameters are set to a default.

        Returns:
            :class:`~pypeit.images.detector_container.DetectorContainer`:
            Object with the detector metadata.
        """
        # Binning
        binning = '1,1' if hdu is None else self.get_meta_value(self.get_headarr(hdu), 'binning')

        # Detector 1 (this all needs checking for a final version)
        detector_dict = dict(
            binning         = binning,
            det              =1,
            dataext         = 0,
            specaxis        = 1, #check this, opposite of xshooter?
            specflip        = False, # check this
            spatflip        = False, # check this
            platescale      = 0.23, # taken from NTE_NOT 2022 presentation slides
            darkcurr        = 0.0,
            saturation      = 65535., # check
            nonlinear       = 0.86, # check
            mincounts       = -1e10,
            numamplifiers   = 1,
            gain            = np.atleast_1d(0.595), # Get this value
            ronoise         = np.atleast_1d(3.0), # Get this value
            datasec=np.atleast_1d('[{}:{},:]'.format(1,1024)),  # Just trying something here
            oscansec= None ,  # Overscan not actually required
        )

        return detector_container.DetectorContainer(**detector_dict)

    @classmethod
    def default_pypeit_par(cls):
        """
        Return the default parameters to use for this instrument.

        Returns:
            :class:`~pypeit.par.pypeitpar.PypeItPar`: Parameters required by
            all of ``PypeIt`` methods.
        """
        par = super().default_pypeit_par()

        # Adjustments to parameters for VIS
        #turn_on = dict(use_biasimage=True, use_overscan=False, overscan_method='median',
        #               use_darkimage=False, use_illumflat=False, use_pixelflat=False,
        #               use_specillum=False)
        turn_off = dict(use_overscan=False)
        par.reset_all_processimages_par(**turn_off)

        # The below is sufficient for OK edge tracing, probably not a necessary set
        par['calibrations']['slitedges']['edge_thresh'] = 3.0
        par['calibrations']['slitedges']['fit_order'] = 5
        par['calibrations']['slitedges']['max_shift_adj'] = 0.5
        par['calibrations']['slitedges']['trace_thresh'] = 3.0
        par['calibrations']['slitedges']['fit_min_spec_length'] = 0.1
        par['calibrations']['slitedges']['length_range'] = 0.3

        par['calibrations']['slitedges']['det_buffer'] = 1
        par['calibrations']['slitedges']['max_nudge'] = 1
        #par['calibrations']['slitedges']['left_right_pca'] = False
        #par['calibrations']['slitedges']['add_slits'] = "1:2280:35:124"
        #par['calibrations']['slitedges']['sync_predict'] = "nearest"
        par['calibrations']['slitedges']['smash_range'] = [0.3,0.7]
        #par['calibrations']['slitedges']['sobel_mode'] = "constant"


        # Start on wl calib
        par['calibrations']['wavelengths']['lamps'] = ["HgAr_NTE_UV"]
        par['calibrations']['wavelengths']['rms_threshold'] = 0.4
        par['calibrations']['wavelengths']['sigdetect'] = 2.0
        par['calibrations']['wavelengths']['fwhm'] = 4.0
        par['calibrations']['wavelengths']['n_final'] = 4# [2, 4, 4, 4, 4, 4, 4, 4]
        par['calibrations']['wavelengths']['nreid_min'] = 1 # important
        
        par['calibrations']['wavelengths']['reference'] = 'arc'
        par['calibrations']['wavelengths']['reid_arxiv'] = 'not_nte_uv.fits'
        par['calibrations']['wavelengths']['method'] = 'full_template'
        par['calibrations']['wavelengths']['nsnippet'] = 1 # important

        # Echelle parameters
        par['calibrations']['wavelengths']['echelle'] = True
        par['calibrations']['wavelengths']['ech_nspec_coeff'] = 4
        par['calibrations']['wavelengths']['ech_norder_coeff'] = 4
        par['calibrations']['wavelengths']['ech_sigrej'] = 3.0

        # tilts
        #par['calibrations']['tilts']['spat_order'] =  3
        
        # Flat
        par['calibrations']['flatfield']['slit_illum_finecorr'] = False # turn off for now

        # skysub
        par['reduce']['skysub']['bspline_spacing'] = 1

        # extraction
        par['reduce']['findobj']['maxnumber_sci'] = 1
        par['reduce']['findobj']['maxnumber_std'] = 1


        # Sensitivity function parameters
        par['sensfunc']['algorithm'] = 'IR'
        #par['sensfunc']['polyorder'] = [9, 11, 11, 9, 9, 8, 8, 7, 7, 7, 7, 7, 7, 7, 7]
        #par['sensfunc']['IR']['telgridfile'] = 'TelFit_Paranal_VIS_4900_11100_R25000.fits'

        return par

    @property
    def norders(self):
        """
        Number of orders observed for this spectograph.
        """
        return 4

    @property
    def order_spat_pos(self):
        """
        Return the expected spatial position of each echelle order.
        """

        return np.array(#[0.14648438, 0.29296875, 
            [0.43945312, 0.5859375,
                         0.73242188, 0.859375])


        #np.array([150, 300, 450, 600, 750, 880]) were positions used for UV
        #np.array([177, 323, 446, 563, 665, 770 ,870,960])are positions used for VIS

        # normalised by the detector height

    @property
    def orders(self):
        """
        Return the order number for each echelle order.
        """
        return np.arange(19, 15, -1, dtype=int) # orders 15-8, from NTE_NOT_2022 slides

    @property
    def spec_min_max(self):
        """
        Return the minimum and maximum spectral pixel expected for the
        spectral range of each order.
        """
        spec_min = np.asarray([0]*4)
        spec_max = np.asarray([1000,1000,1000,1000])
        return np.vstack((spec_min, spec_max))
    
#Really don't know what this section will do

    def order_platescale(self, order_vec, binning=None):
        """
        Return the platescale for each echelle order.

        This routine is only defined for echelle spectrographs, and it is
        undefined in the base class.

        Args:
            order_vec (`numpy.ndarray`_):
                The vector providing the order numbers.
            binning (:obj:`str`, optional):
                The string defining the spectral and spatial binning.

        Returns:
            `numpy.ndarray`_: An array with the platescale for each order
            provided by ``order``.
        """
        # VIS has no binning, but for an instrument with binning we would do this
        binspectral, binspatial = parse.parse_binning(binning)

        # ToDO Work this out
        
        # Right now I just assume constant
        plate_scale = np.ones(4) * 0.23 
        return plate_scale*binspatial

        # Not sure about this, commenting out
##    @property
##    def dloglam(self):
##        """
##        Return the logarithmic step in wavelength for output spectra.
##        """
##        # This number was computed by taking the mean of the dloglam for all
##        # the X-shooter orders. The specific loglam across the orders deviates
##        # from this value by +-7% from this first to final order. This is the
##        # unbinned value. It was actually measured to be 1.69207e-5 from a 2x1
##        # data and then divided by two.
##        return 8.46035e-06

    @property
    def loglam_minmax(self):
        """
        Return the base-10 logarithm of the first and last wavelength for
        ouput spectra.
        """
        return np.log10(3000), np.log10(4300)

    def bpm(self, filename, det, shape=None, msbias=None):
        """
        Generate a default bad-pixel mask.

        Even though they are both optional, either the precise shape for
        the image (``shape``) or an example file that can be read to get
        the shape (``filename`` using :func:`get_image_shape`) *must* be
        provided.

        Args:
            filename (:obj:`str` or None):
                An example file to use to get the image shape.
            det (:obj:`int`):
                1-indexed detector number to use when getting the image
                shape from the example file.
            shape (tuple, optional):
                Processed image shape
                Required if filename is None
                Ignored if filename is not None
            msbias (`numpy.ndarray`_, optional):
                Master bias frame used to identify bad pixels

        Returns:
            `numpy.ndarray`_: An integer array with a masked value set
            to 1 and an unmasked value set to 0.  All values are set to
            0.
        """
        # Call the base-class method to generate the empty bpm

        # THE BELOW MASKS OUT THE +/- 1 ORDERS, NOT A REAL BPM AND MAY NOT BE IN THE FINAL CODE
        
        bpm_img = super().bpm(filename, det, shape=shape, msbias=msbias)
        # Should return an empty bpm
        return bpm_img
