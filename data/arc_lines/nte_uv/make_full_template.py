from pypeit.core.wavecal import templates
import glob

wavelength_soln_files = glob.glob("./wvcalib*.fits")

wavelength_soln_files = [
    "wvcalib_order19_5.fits", # [3644.0,     3297.0]
    "wvcalib_order18_5.fits", # [3857.0,     3470.0],
    "wvcalib_order17_5.fits", # [4096.0,     3662.0],
    "wvcalib_order16_5.fits", # [4366.0,     3877.0],
                         ]

slits = [
         #49,188,313,429,538,641,739,836 # THIS FOR UNMASKED
         #82,198,323,439,548,651,749,845 # THIS FOR MASKED
         453,604,745,870  # This is a blend
         
         ]

wv_cuts = [
    3555, 3750, 3920
    ]

binspec = 1
outroot = "not_nte_uv_5.fits"
#print(wavelength_soln_files)

templates.build_template(wavelength_soln_files,
                         slits,
                         wv_cuts,
                         binspec,
                         outroot,
                         #ifiles=ifiles,
                         #det_cut=det_cut,
                         chk=True,
                         normalize=False,
                         lowredux=False,
                         subtract_conti=True,
                         #overwrite=overwrite,
                         shift_wave=True,
                         in_vac=False)
