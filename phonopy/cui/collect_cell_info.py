# Copyright (C) 2018 Atsushi Togo
# All rights reserved.
#
# This file is part of phonopy.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in
#   the documentation and/or other materials provided with the
#   distribution.
#
# * Neither the name of the phonopy project nor the names of its
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import numpy as np
from phonopy.interface.calculator import (
    read_crystal_structure, get_default_cell_filename)
from phonopy.interface.vasp import read_vasp


def collect_cell_info(supercell_matrix=None,
                      primitive_matrix=None,
                      interface_mode=None,
                      cell_filename=None,
                      chemical_symbols=None,
                      enforce_primitive_matrix_auto=False,
                      command_name="phonopy",
                      symprec=1e-5):
    # In some cases, interface mode falls back to phonopy_yaml mode.
    fallback_reason = _fallback_to_phonopy_yaml(
        supercell_matrix,
        interface_mode,
        cell_filename)

    if fallback_reason:
        _interface_mode = 'phonopy_yaml'
    elif interface_mode is None:
        _interface_mode = None
    else:
        _interface_mode = interface_mode.lower()

    unitcell, optional_structure_info = read_crystal_structure(
        filename=cell_filename,
        interface_mode=_interface_mode,
        chemical_symbols=chemical_symbols,
        command_name=command_name)

    # Error check
    if unitcell is None:
        err_msg = _get_error_message(optional_structure_info,
                                     interface_mode,
                                     fallback_reason,
                                     cell_filename,
                                     command_name)
        return err_msg

    # Retrieve more information on cells
    (interface_mode_out,
     supercell_matrix_out,
     primitive_matrix_out) = _collect_cells_info(
         _interface_mode,
         optional_structure_info,
         command_name,
         interface_mode,
         supercell_matrix,
         primitive_matrix,
         enforce_primitive_matrix_auto)

    # Another error check
    msg_list = ["Crystal structure was read from \"%s\"."
                % optional_structure_info[0], ]
    if supercell_matrix_out is None:
        msg_list.append(
            "Supercell matrix (DIM or --dim) information was not found.")
        return "\n".join(msg_list)

    if np.linalg.det(unitcell.get_cell()) < 0.0:
        msg_list.append("Lattice vectors have to follow the right-hand rule.")
        return "\n".join(msg_list)

    # Succeeded!
    return (unitcell, supercell_matrix_out, primitive_matrix_out,
            optional_structure_info, interface_mode_out,
            interface_mode_out == 'phonopy_yaml')


def _fallback_to_phonopy_yaml(supercell_matrix,
                              interface_mode,
                              cell_filename):
    """Find possibility to fallback to phonopy.yaml mode

    When fallback happens.

    1. supercell_matrix is not given
    2. parsing default VASP style crystal structure failed

    Parameters
    ----------
    supercell_matrix : array_like or None
        None is given when phonopy.yaml mode is expected.
    interface_mode : str or None
        None is the default mode, i.e., VASP like.
    cell_filename : str or None
        File name of VASP style crystal structure. None means the default
        file name, "POSCAR".

    Returns
    -------
    fallback_reason : str or None
        This provides information how to handle after the fallback.
        None means fallback to phonopy.yaml mode will not happen.

    """

    fallback_reason = None

    if interface_mode is None:
        fallback_reason = _poscar_failed(cell_filename)

    if fallback_reason is not None:
        if supercell_matrix is None:
            fallback_reason = "no supercell matrix given"

    return fallback_reason


def _poscar_failed(cell_filename):
    fallback_reason = None
    try:
        if cell_filename is None:
            read_vasp(get_default_cell_filename('vasp'))
        else:
            read_vasp(cell_filename)
    except ValueError:
        # read_vasp parsing failed.
        fallback_reason = "read_vasp parsing failed"
    except FileNotFoundError:
        if cell_filename is None:
            fallback_reason = "default file not found"
        else:
            # Given file with cell_filename not found.
            #
            # In this case, do nothing, i.e., fallback_reason = None.
            # This error is handled in the following part
            # (read_crystal_structure).
            pass
    return fallback_reason


def _collect_cells_info(_interface_mode,
                        optional_structure_info,
                        command_name,
                        interface_mode,
                        supercell_matrix,
                        primitive_matrix,
                        enforce_primitive_matrix_auto):
    """This is a method just to wrap up and exclude dirty stuffs."""

    if (_interface_mode == 'phonopy_yaml' and
        optional_structure_info[1] is not None):
        phpy = optional_structure_info[1]
        calculator = None
        if command_name in phpy.yaml:
            if 'calculator' in phpy.yaml[command_name]:
                calculator = phpy.yaml[command_name]['calculator']
        if ('supercell_matrix' in phpy.yaml and
            phpy.yaml['supercell_matrix'] is not None):
            smat = phpy.supercell_matrix
        else:
            smat = None
        if ('primitive_matrix' in phpy.yaml and
            phpy.yaml['primitive_matrix'] is not None):
            pmat = phpy.primitive_matrix
        else:
            pmat = None

        if calculator is None:
            interface_mode_out = interface_mode
        else:
            interface_mode_out = calculator
        if smat is None:
            _supercell_matrix = supercell_matrix
        else:
            _supercell_matrix = smat
        if primitive_matrix is not None:
            _primitive_matrix = primitive_matrix
        elif pmat is not None:
            _primitive_matrix = pmat
        else:
            _primitive_matrix = 'auto'
    else:
        interface_mode_out = _interface_mode
        _supercell_matrix = supercell_matrix
        _primitive_matrix = primitive_matrix

    if enforce_primitive_matrix_auto:
        _primitive_matrix = 'auto'

    if _supercell_matrix is None and _primitive_matrix == 'auto':
        supercell_matrix_out = np.eye(3, dtype='intc')
    else:
        supercell_matrix_out = _supercell_matrix

    primitive_matrix_out = _primitive_matrix

    return interface_mode_out, supercell_matrix_out, primitive_matrix_out


def _get_error_message(optional_structure_info,
                       interface_mode,
                       fallback_reason,
                       cell_filename,
                       command_name):
    final_cell_filename = optional_structure_info[0]

    if fallback_reason is None:
        msg_list = []
        if cell_filename != final_cell_filename:
            msg_list.append("Crystal structure file \"%s\" was not found."
                            % cell_filename)
        msg_list.append("Crystal structure file \"%s\" was not found."
                        % final_cell_filename)
        return "\n".join(msg_list)

    ####################################
    # Must be phonopy_yaml mode below. #
    ####################################

    msg_list = []
    if fallback_reason in ["default file not found",
                           "read_vasp parsing failed"]:
        if cell_filename:
            vasp_filename = cell_filename
        else:
            vasp_filename = get_default_cell_filename('vasp')

        if fallback_reason == "read_vasp parsing failed":
            msg_list.append(
                "Parsing crystal structure file of \"%s\" failed."
                % vasp_filename)
        else:
            msg_list.append(
                "Crystal structure file of \"%s\" was not found."
                % vasp_filename)

    elif fallback_reason == "no supercell matrix given":
        msg_list.append("Supercell matrix (DIM or --dim) was not explicitly "
                        "specified.")

    msg_list.append("By this reason, phonopy_yaml mode was invoked.")

    if final_cell_filename is None:  # No phonopy*.yaml file was found.
        msg_list.append("But \"%s\" and \"%s\" could not be found."
                        % ("%s_disp.yaml" % command_name,
                           "%s.yaml" % command_name))
        return "\n".join(msg_list)

    phpy = optional_structure_info[1]
    if phpy is None:  # Failed to parse phonopy*.yaml.
        msg_list.append("But parsing \"%s\" failed." % final_cell_filename)

    return "\n".join(msg_list)
