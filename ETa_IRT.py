import warnings
import numpy as np
import pandas as pd

def calc_NDVI(Nir, Red):
    """
    Calculates calc_NDVI.

    :param Nir: Nir band value.
    :param Red: Red band value.

    :return: calc_NDVI value.
    """
    return (Nir - Red) / (Nir + Red)


def scale_NDVI(NDVI, NDVI_max=0.90, NDVI_min=0.15):
    """
    Scale calc_NDVI value based on a min an max value.

    :param NDVI: calc_NDVI value to scale.
    :param NDVI_max: Max calc_NDVI value. Default set to 0.90.
    :param NDVI_min: Min calc_NDVI value.Default set to 0.15.

    :return: scaled calc_NDVI value.
    """
    scaled_NDVI = (NDVI - NDVI_min) / (NDVI_max - NDVI_min)

    return scaled_NDVI


def fractional_veg_cover(scaled_NDVI):
    """
    Estimates fraction vegetation/crop cover with the given scaled scaled calc_NDVI value.
    Must be within [0, 1].

    :param scaled_NDVI: scaled calc_NDVI value.

    :return: fractional crop cover value.
    """
    Fr = scaled_NDVI ** 2

    if Fr < 0:
        warnings.warn(f"Fractional crop cover value {Fr} is less than 0. Setting it to 0")

        Fr = 0

    elif Fr > 1:
        warnings.warn(f"Fractional crop cover value {Fr} is greater than 1. Setting it to 1")

        Fr = 1

    return Fr


def calc_target_emissivity(Fr, veg_emissivity=0.98, soil_emissivity=0.93):
    """
    Estimates surface/target (for the pixel) emissivity.

    :param Fr: Fractional crop cover value
    :param veg_emissivity: Default set to 0.98 for full cover, green, healthy plant.
    :param soil_emissivity: Default set to 0.93 for bare soil.

    :return: Surface/target emissivity value.
    """

    target_emissivity = Fr * veg_emissivity + (1 - Fr) * soil_emissivity

    return target_emissivity


def adj_target_T(T_sensor, target_emissivity, T_background=-15):
    """
    Calculates actual target temperature (measures brightness temperature) that is adjusted for background temperature
    (sky) and adjusted surface emissivity.

    :param T_sensor: Sensor's unadjusted temperature. Unit is Deg C.
    :param target_emissivity: Adjusted emissivity (for vegetation and bare soil) of the target.
    :param T_background: Background (sky) temperature. Needed to adjust for it as it crates reflected radiance from
                         surface which shouldn't  be considered in the adjusted temperature of the target.
                         Default set to -15 deg C.

    :return: adjusted target temperature.
    """

    T_target = ((T_sensor ** 4 - (1 - target_emissivity) * (T_background) ** 4) / target_emissivity) ** 0.25

    return T_target


def calc_esat(T):
    """
    Calculate saturation vapor pressure from temperature.

    :param T: Temperature (deg C).

    :return: Saturation vapor pressure (kPa).
    """
    esat = 0.6108 * np.exp(17.27 * T / (T + 237.3))

    return esat


def calc_ea(T, RH):
    """
    calculated actual vapor pressure.

    :param T: Temperature (deg C).
    :param RH: Relative humidity (in %).

    :return: Actual vapor pressure (kpa).
    """
    esat = calc_esat(T)

    ea = RH * esat / 100

    return ea


def calc_VPD(esat, ea):
    """
    Calculate vapor pressure deficit.

    :param esat: Saturation vapor pressure (kPa).
    :param ea: Actual vapor pressure (kPa).

    :return: Vapor pressure deficit (kPa).
    """
    VPD = esat - ea

    return VPD


def calc_VPG(esat, T):
    """
    Calculate vapor pressure gradient.

    ******
    VPG here represents the rate of change of vapor pressure with temperature. It gives an idea of how quickly vapor
    pressure changes as temperature changes. This gradient is relevant for understanding how temperature variations can
    influence water vapor content and can be particularly useful in modeling processes where temperature variations
    affect humidity and water availability.

    :param esat: Saturation vapor pressure (kPa).
    :param Tc: Temperature of saturation (deg C).

    :return: Vapor pressure gradient (kPa). Value i going to ne (-)ve.
    """
    esat_b = calc_esat(T + 3.11)  # 3.11 is the b value from Idso (1982) dTmin formula. dTmin = 3.11 - 1.97 * VPD

    VPG = esat - esat_b

    return VPG


def calc_idso_dTmin(VPD):
    """
    Calculated Idso (1982) dTmin for CWSI plot.

    :param VPD: Vapor pressure deficit (kpa).

    :return: dTmin value.
    """
    dTmin = 3.11 - 1.97 * VPD

    return dTmin


def calc_idso_dTmax(VPG):
    """
    Calculated Idso (1982) dTmax for CWSI plot.

    :param VPG: Vapor pressure gradient (kpa).

    :return: dTmax value.
    """
    dTmax = 3.11 - 1.97 * VPG

    return dTmax


def calc_CWSI(dTmin, dTmax, Ta, T_target):
    """
    Calculates crop water stress index (CWSI).

    :param dTmin: Calculated dTmin value using VPD using Idso (1982).
    :param dTmax: Calculated dTmax value using VPG using Idso (1982)
    :param Ta: Weather station temperature or reference air temperature (deg C).
    :param T_target: Target temperature (corrected from adj_target_T() function) (deg C).

    :return: CWSI value.
    """

    dT = T_target - Ta

    CWSI = (dT - dTmin)/ (dTmax - dTmin)

    return CWSI


def calc_ETa(CWSI, ETc):
    """
    Calculates ETa (actual) based on CWSI and ETc.

    :param CWSI: Crop water stress index value.
    :param ETc: Potential evapotranspiration.

    :return: ETa value. Unit depends on the unit of ETc.
    """
    ETa = (1 - CWSI) * ETc

    return ETa


def calc_CWSI_ETa(Nir, Red, T_sensor, RH, Ta, ETc):
    """
    Runs calculations to obtain Crop Water Stress Index (CWSI) and actual evapotranspiration (ETa).

    :param Nir: Near-infrared (NIR) band value.
    :param Red: Red band value.
    :param T_sensor: Sensor's measured surface temperature (in °C).
    :param RH: Relative humidity (%).
    :param Ta: Air temperature (in °C), typically from a weather station.
    :param ETc: Potential evapotranspiration (ETc) value.

    :return: Tuple containing values for NDVI, scaled NDVI, fractional vegetation cover (Fr), target emissivity,
             corrected target temperature (T_target), saturation vapor pressure (esat), actual vapor pressure (ea),
             vapor pressure deficit (VPD), vapor pressure gradient (VPG), dTmin, dTmax, CWSI, and ETa.
    """

    # correcting sensor's temperature
    NDVI = calc_NDVI(Nir, Red)
    NDVI_scaled = scale_NDVI(NDVI, NDVI_max=0.90, NDVI_min=0.15)
    Fr = fractional_veg_cover(NDVI_scaled)
    target_emissivity = calc_target_emissivity(Fr, veg_emissivity=0.98, soil_emissivity=0.93)
    T_target = adj_target_T(T_sensor, target_emissivity, T_background=-15)

    # calculating VPD (using weather station/actual air temperature)
    esat = calc_esat(Ta)
    ea = calc_ea(Ta, RH)
    vpd = calc_VPD(esat, ea)

    # calculating VPG (using weather station/actual air temperature)
    vpg = calc_VPG(esat, Ta)

    # calculating dTmin and dTmax
    dTmin = calc_idso_dTmin(vpd)
    dTmax = calc_idso_dTmax(vpg)

    # calculating CWSI and ETa
    cwsi = calc_CWSI(dTmin, dTmax, Ta, T_target)
    ETa = calc_ETa(cwsi, ETc)

    # print(f'{target_emissivity=}, {T_target=}, {esat=}, {ea=}, {vpd=}, {vpg=}, {dTmin=}, {dTmax=}, {cwsi=}, {ETa=}')

    return NDVI, NDVI_scaled, Fr, target_emissivity, T_target, esat, ea, vpd, vpg, dTmin, dTmax, cwsi, ETa


def run_CWSI_ETa_model(input_csv, output_csv, Nir_col='R_nir', Red_col='R_red',
                       T_sensor_col='T_target', RH_col='RH', Ta_col='Air Temp',
                       ETc_col='ETc'):
    """
    Runs the model to calculate CWSI and ETa for each row in an input csv file and saves the results to an output csv
    file.

    :param input_csv: Path to the input CSV file containing required data.
    :param output_csv: Path to the output CSV file where results will be saved.
    :param Nir_col: Column name for Near-infrared (NIR) band value in the input CSV. Default is 'R_nir'.
    :param Red_col: Column name for Red band value in the input CSV. Default is 'R_red'.
    :param T_sensor_col: Column name for the sensor's surface temperature in the input CSV. Default is 'T_target'.
    :param RH_col: Column name for relative humidity in the input CSV. Default is 'RH'.
    :param Ta_col: Column name for air temperature in the input CSV. Default is 'Air Temp'.
    :param ETc_col: Column name for potential evapotranspiration (ETc) in the input CSV. Default is 'ETc'.

    :return: None. The function saves the calculated values in the output csv file.
    """
    input_df = pd.read_csv(input_csv)

    output_df = input_df.copy()

    # initializing empty lists to assign values calculated during the model
    NDVI_list = []
    NDVI_scaled_list = []
    Fr_list = []
    emissivity_list = []
    T_target_list = []
    vpd_list = []
    vpg_list = []
    dTmin_list = []
    dTmax_list = []
    cwsi_list = []
    ETa_list = []

    for idx, row in output_df.iterrows():
        # calculating requried values for each row
        NDVI, NDVI_scaled, Fr, target_emissivity, T_target, esat, ea, vpd, vpg, dTmin, dTmax, cwsi, ETa = \
            calc_CWSI_ETa(Nir=row[Nir_col], Red=row[Red_col], T_sensor=row[T_sensor_col],
                          RH=row[RH_col], Ta=row[Ta_col], ETc=row[ETc_col])

        # assiging values to the lists
        NDVI_list.append(NDVI)
        NDVI_scaled_list.append(NDVI_scaled)
        Fr_list.append(Fr)
        emissivity_list.append(target_emissivity)
        T_target_list.append(T_target)
        vpd_list.append(vpd)
        vpg_list.append(vpg)
        dTmin_list.append(dTmin)
        dTmax_list.append(dTmax)
        cwsi_list.append(cwsi)
        ETa_list.append(ETa)

    # adding the estimated values in the dataframe
    output_df.loc[:, 'NDVI'] = NDVI_list
    output_df.loc[:, 'NDVI_scaled'] = NDVI_scaled_list
    output_df.loc[:, 'Fr'] = Fr_list
    output_df.loc[:, 'target_emissivity'] = emissivity_list
    output_df.loc[:, 'T_target_corr'] = T_target_list
    output_df.loc[:, 'VPD'] = vpd_list
    output_df.loc[:, 'VPG'] = vpg_list
    output_df.loc[:, 'dTmin'] = dTmin_list
    output_df.loc[:, 'dTmax'] = dTmax_list
    output_df.loc[:, 'CWSI'] = cwsi_list
    output_df.loc[:, 'ETa'] = ETa_list

    output_df.to_csv(output_csv, index=False)
