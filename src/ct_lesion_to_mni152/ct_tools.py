import os

import SimpleITK as sitk
import numpy as np
from skimage.filters import threshold_otsu
from skimage import measure
from scipy import ndimage
from skimage import exposure


def extract_skull(ct_img_path: str, output_dir: str, output_name: str) -> str:
    """
    Extract the skull of the CT scan based on the hard thresholding on pixel value
    """

    print(("CT scan to extract skull from: ", ct_img_path))

    ct_img = sitk.ReadImage(ct_img_path)
    skull_mask_img = sitk.Image(
        ct_img.GetWidth(), ct_img.GetHeight(), ct_img.GetDepth(), sitk.sitkFloat32
    )
    output_ct_img = sitk.Image(
        ct_img.GetWidth(), ct_img.GetHeight(), ct_img.GetDepth(), sitk.sitkFloat32
    )

    print(("The size of CT scan:", ct_img.GetSize()))

    ct_nda = sitk.GetArrayFromImage(ct_img)
    skull_mask_nda = sitk.GetArrayFromImage(skull_mask_img)
    output_ct_nda = sitk.GetArrayFromImage(output_ct_img)

    # print 'The minimum value of CT scan: ', np.amin(ct_nda)
    # print 'The maximum value of CT scan: ', np.amax(ct_nda)
    # print 'The pixel ID type of CT scan: ', ct_img.GetPixelIDTypeAsString()
    # m = 1.0
    # b = -1024.0
    # bone_HU = 500.0
    # bone_pixel = (bone_HU-b)/m

    bone_pixel = 500

    for z in range(ct_nda.shape[0]):
        for x in range(ct_nda.shape[1]):
            for y in range(ct_nda.shape[2]):
                if ct_nda[z, x, y] >= bone_pixel:
                    output_ct_nda[z, x, y] = ct_nda[z, x, y]
                    skull_mask_nda[z, x, y] = 1.0

    output_ct_image = sitk.GetImageFromArray(output_ct_nda)
    output_ct_image_path = os.path.join(
        output_dir,
        output_name,
    )

    print("Name of the output skull image: ", output_ct_image_path)
    output_ct_image.CopyInformation(ct_img)
    sitk.WriteImage(output_ct_image, output_ct_image_path)

    return output_ct_image_path

    # bone_mask
    # bone_mask_image = sitk.GetImageFromArray(bone_mask_nda)
    # bone_mask_image_name = ct_img_path[:ct_img_path.find('.nii.gz')]+'_skullMask.nii.gz'
    # bone_mask_image.CopyInformation(ct_img)

    # print 'The name of the output skull mask image: ', bone_mask_image_name
    # sitk.WriteImage(bone_mask_image, bone_mask_image_name)

    # return output_ct_image_name, bone_mask_image_name


def get_maximum_3d_region(binary):
    """Get the Maximum 3D region from 3D multiple binary Regions"""

    all_labels = measure.label(binary, background=0)
    props = measure.regionprops(all_labels)
    areas = [prop.area for prop in props]
    maxArea_label = 1 + np.argmax(areas)
    max_binary = np.float32(all_labels == maxArea_label)

    return max_binary


def normalize_ct_scan(ct_nda: np.ndarray) -> np.ndarray:
    """Normalize the CT scan to range 0 to 1"""
    if np.amin(ct_nda) < 0:
        ct_normalized_nda = ct_nda - np.amin(ct_nda)

    ct_normalized_nda = ct_normalized_nda / np.amax(ct_normalized_nda)

    return ct_normalized_nda


def otsu_thresholding(ct_normalized_nda: np.ndarray) -> np.ndarray:
    """Apply Otsu thresholding on the normalized ranging from 0 to 1 scan"""

    thresh = threshold_otsu(ct_normalized_nda)
    binary = (ct_normalized_nda > thresh) * 1

    return binary.astype(np.float32)


def get_2_maximum_2d_regions(max_binary: np.ndarray):
    """Get two largestest 2D region from multiple 2D regions"""

    xy_two_largest_binary = np.zeros(max_binary.shape, dtype=np.float32)
    largest_area = np.zeros(max_binary.shape[0])
    second_largest_area = np.zeros(max_binary.shape[0])

    for i in range(max_binary.shape[0]):
        xy_binary = max_binary[i, :, :]
        xy_labels = measure.label(xy_binary, background=0)
        xy_props = measure.regionprops(xy_labels)
        xy_areas = [prop.area for prop in xy_props]
        # print xy_areas

        if xy_areas == []:
            continue

        elif len(xy_areas) == 1:
            largest_area[i] = xy_areas[0]
            second_largest_area[i] = 0.0
            largest_label = xy_areas.index(largest_area[i]) + 1
            xy_two_largest_binary[i, :, :] = xy_labels == largest_label

        else:
            xy_areas_sorted = sorted(xy_areas)
            largest_area[i] = xy_areas_sorted[-1]
            second_largest_area[i] = xy_areas_sorted[-2]
            largest_label = xy_areas.index(largest_area[i]) + 1
            second_largest_label = xy_areas.index(second_largest_area[i]) + 1
            xy_largest_binary = xy_labels == largest_label
            xy_second_largest_binary = xy_labels == second_largest_label
            xy_two_largest_binary[i, :, :] = np.float32(
                np.logical_or(xy_largest_binary, xy_second_largest_binary)
            )

    return xy_two_largest_binary


def get_1_maximum_2d_region(max_second_binary: np.ndarray):
    """Get the largest 2D region from multiple 2D regions"""

    new_binary = np.zeros(max_second_binary.shape, dtype=np.float32)
    for i in range(max_second_binary.shape[0]):
        xy_binary = max_second_binary[i, :, :]
        xy_labels = measure.label(xy_binary)
        xy_props = measure.regionprops(xy_labels)
        xy_areas = [prop.area for prop in xy_props]
        # print i, xy_areas_1
        if xy_areas == []:
            continue
        else:
            max_area_label = 1 + np.argmax(xy_areas)
            new_binary[i, :, :] = np.float32(xy_labels == max_area_label)

    return new_binary


def image_opening_2d(
    max_second_binary: np.ndarray, structure: np.ndarray = np.ones((15, 15))
):
    """Applying the image opening operation on the binary mask"""

    new_max_second_binary = np.zeros(max_second_binary.shape, dtype=np.float32)

    for i in range(max_second_binary.shape[0]):
        new_max_second_binary[i, :, :] = ndimage.binary_opening(
            max_second_binary[i, :, :].astype(int), structure=structure
        ).astype(np.float32)

    return new_max_second_binary


def remove_ct_scan_device(ct_img_path: str, output_dir: str, output_name: str) -> str:
    """remove the ct scan device"""

    ct_img = sitk.ReadImage(ct_img_path)
    ct_nda = sitk.GetArrayFromImage(ct_img)

    print(("CT scan to remove scan device from:", ct_img_path))

    ct_normalized_nda = normalize_ct_scan(ct_nda)
    binary = otsu_thresholding(ct_normalized_nda)
    max_binary = get_maximum_3d_region(binary)
    xy_two_largest_binary = get_2_maximum_2d_regions(max_binary)
    max_second_binary = get_maximum_3d_region(xy_two_largest_binary)
    new_binary = get_1_maximum_2d_region(max_second_binary)
    new_max_second_bindary = image_opening_2d(new_binary)
    new_max_binary = get_maximum_3d_region(new_max_second_bindary)
    output_ct_image = sitk.GetImageFromArray(ct_nda * new_max_binary)
    output_ct_image.CopyInformation(ct_img)
    output_ct_image_path = os.path.join(
        output_dir,
        output_name,
        # _woCTdevice.nii.gz
    )
    sitk.WriteImage(output_ct_image, output_ct_image_path)

    return output_ct_image_path


def contrast_stretch(
    ct_img_path: str, output_dir: str, output_name: str, percent: tuple = (10, 90)
) -> str:
    """Apply the contrast stretching on 2D or 3D image"""

    ct_img = sitk.ReadImage(ct_img_path)
    ct_nda = sitk.GetArrayFromImage(ct_img)
    p1, p2 = np.percentile(ct_nda, percent, interpolation="nearest")
    nda_rescale = exposure.rescale_intensity(ct_nda, in_range=(p1, p2))
    ct_img_cs = sitk.GetImageFromArray(nda_rescale)
    ct_img_cs.CopyInformation(ct_img)
    output_ct_image_path = os.path.join(output_dir, output_name)
    sitk.WriteImage(ct_img_cs, output_ct_image_path)

    return output_ct_image_path
