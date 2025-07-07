import sys
import os
import csv
import codecs
from ij import IJ
from fiji.plugin.trackmate import Model, Settings, TrackMate, Logger
from fiji.plugin.trackmate.detection import LogDetectorFactory, DogDetectorFactory
from fiji.plugin.trackmate.tracking.jaqaman import SparseLAPTrackerFactory
from fiji.plugin.trackmate.gui.displaysettings import DisplaySettingsIO
from fiji.plugin.trackmate.gui.displaysettings.DisplaySettings import TrackMateObject
from fiji.plugin.trackmate.features.track import TrackIndexAnalyzer
import fiji.plugin.trackmate.visualization.hyperstack.HyperStackDisplayer as HyperStackDisplayer
import fiji.plugin.trackmate.features.FeatureFilter as FeatureFilter
from java.awt import Color  # マゼンタ指定に必要

reload(sys)
sys.setdefaultencoding('utf-8')


def run_trackmate_on_image(imp, detector='Log', spot_filters=[], display_spot=True, display_track=True):
    model = Model()
    model.setLogger(Logger.IJ_LOGGER)

    settings = Settings(imp)

    if detector == 'Log':
        settings.detectorFactory = LogDetectorFactory()
    elif detector == 'DoG':
        settings.detectorFactory = DogDetectorFactory()
    else:
        sys.exit("Unsupported detector: " + detector)

    settings.detectorSettings = {
        'DO_SUBPIXEL_LOCALIZATION': True,
        'RADIUS': 0.15,
        'TARGET_CHANNEL': 1,
        'THRESHOLD': 1.0,
        'DO_MEDIAN_FILTERING': True,
    }

    for f in spot_filters:
        settings.addSpotFilter(FeatureFilter(f['feature'], f['value'], f['is_above']))

    settings.trackerFactory = SparseLAPTrackerFactory()
    tracker_settings = settings.trackerFactory.getDefaultSettings()
    
    tracker_settings['LINKING_MAX_DISTANCE'] = 0.1
    tracker_settings['GAP_CLOSING_MAX_DISTANCE'] = 0.4
    tracker_settings['SPLITTING_MAX_DISTANCE'] = 15.0
    tracker_settings['MERGING_MAX_DISTANCE'] = 0.2

    tracker_settings['ALLOW_GAP_CLOSING'] = False
    tracker_settings['ALLOW_TRACK_SPLITTING'] = False
    tracker_settings['ALLOW_TRACK_MERGING'] = False

    tracker_settings['MAX_FRAME_GAP'] = 3
    tracker_settings['ALTERNATIVE_LINKING_COST_FACTOR'] = 1.05
    tracker_settings['BLOCKING_VALUE'] = float('inf')
    tracker_settings['CUTOFF_PERCENTILE'] = 0.9

    tracker_settings['LINKING_FEATURE_PENALTIES'] = {}
    tracker_settings['GAP_CLOSING_FEATURE_PENALTIES'] = {}
    tracker_settings['MERGING_FEATURE_PENALTIES'] = {}
    tracker_settings['SPLITTING_FEATURE_PENALTIES'] = {}

    settings.trackerSettings = tracker_settings
    settings.addAllAnalyzers()

    trackmate = TrackMate(model, settings)
    if not trackmate.checkInput():
        sys.exit(str(trackmate.getErrorMessage()))
    if not trackmate.process():
        sys.exit(str(trackmate.getErrorMessage()))

    model.getLogger().log("Total spots after filtering: %d" % model.getSpots().getNSpots(True))

    display_results(model, imp, display_spot, display_track)
    return model


def display_results(model, imp, display_spot=True, display_track=True):
    from fiji.plugin.trackmate import SelectionModel
    sm = SelectionModel(model)
    ds = DisplaySettingsIO.readUserDefault()

    if display_track:
        ds.setTrackVisible(True)
        ds.setTrackColorBy(TrackMateObject.TRACKS, TrackIndexAnalyzer.TRACK_INDEX)
    else:
        ds.setTrackVisible(False)

    if display_spot:
        ds.setSpotVisible(True)
        #ds.setSpotColorBy(TrackMateObject.TRACKS, TrackIndexAnalyzer.TRACK_INDEX)
    else:
        ds.setSpotVisible(False)

    displayer = HyperStackDisplayer(model, sm, imp, ds)
    displayer.render()
    displayer.refresh()


def export_spots_to_csv(model, output_csv_path):
    tracks = model.getTrackModel()
    all_spots = model.getSpots()

    header = [
        'Track_ID', 'Spot_ID', 'Frame', 'Position_X', 'Position_Y', 'Position_Z',
        'Radius', 'Quality', 'Mean_Intensity_Ch1', 'Max_Intensity_Ch1', 'Median_Intensity_Ch1',
        'SNR_Ch1', 'Contrast_Ch1'
    ]

    def safe_get(spot, feature):
        value = spot.getFeature(feature)
        if value is None:
            return ''
        if isinstance(value, float):
            return "%.3f" % value
        return str(value)

    # Spot ID → Track ID マッピング
    spot_to_track = {}
    for track_id in tracks.trackIDs(False):
        for spot in tracks.trackSpots(track_id):
            spot_to_track[spot.ID()] = track_id

    with codecs.open(output_csv_path, 'w', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for spot in all_spots.iterator(True):  # フレーム順
            spot_id = spot.ID()
            track_id = spot_to_track.get(spot_id, -1)

            frame_raw = spot.getFeature('FRAME')
            frame = ''
            if frame_raw is not None:
                try:
                    frame = int(round(float(frame_raw)))
                except:
                    frame = ''

            row = [
                track_id,
                spot_id,
                frame,
                safe_get(spot, 'POSITION_X'),
                safe_get(spot, 'POSITION_Y'),
                safe_get(spot, 'POSITION_Z'),
                safe_get(spot, 'RADIUS'),
                safe_get(spot, 'QUALITY'),
                safe_get(spot, 'MEAN_INTENSITY_CH1'),
                safe_get(spot, 'MAX_INTENSITY_CH1'),
                safe_get(spot, 'MEDIAN_INTENSITY_CH1'),
                safe_get(spot, 'SNR_CH1'),
                safe_get(spot, 'CONTRAST_CH1'),
            ]
            writer.writerow(row)


def batch_process(input_folder, output_folder, detector='Log', spot_filters=[], display_spot=False, display_track=False):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(".tif") or filename.lower().endswith(".tiff"):
            filepath = os.path.join(input_folder, filename)
            IJ.log("Processing: " + filepath)
            imp = IJ.openImage(filepath)
            if imp is None:
                IJ.log("Failed to open: " + filepath)
                continue

            imp.show()

            # --- ZスタックをT系列に変換（T>1の画像は変換しない） ---
            n_channels = imp.getNChannels()
            n_slices = imp.getNSlices()  # Z
            n_frames = imp.getNFrames()  # T

            if n_slices > 1 and n_frames == 1:
                IJ.log("Z>1 and T=1 detected. Converting Z-stack to time series...")
                imp.setDimensions(n_channels, 1, n_slices)


            model = run_trackmate_on_image(
                imp,
                detector=detector,
                spot_filters=spot_filters,
                display_spot=display_spot,
                display_track=display_track
            )

            csv_name = os.path.splitext(filename)[0] + '_allspots.csv'
            csv_path = os.path.join(output_folder, csv_name)
            export_spots_to_csv(model, csv_path)

            imp.changes = False
            # imp.close()


########## 実行設定 ##########

input_path = '/Users/Kimura-Lab/Desktop/Trackmate/Images/'
output_path = '/Users/Kimura-Lab/Desktop/Trackmate/csv/'

filters = [
    {'feature': 'QUALITY', 'value': 1.0, 'is_above': True},
    {'feature': 'CONTRAST_CH1', 'value': 0.020, 'is_above': True},
]

batch_process(
    input_folder=input_path,
    output_folder=output_path,
    detector='Log',
    spot_filters=filters,
    display_spot=True,
    display_track=False
)
