import configparser
import re
from collections import namedtuple

OTO = namedtuple('OTO', 'wav prefix alien suffix l con r pre ovl')
VSDXMF = namedtuple('VSDXMF', 'phoneme wav l pre con r ovl')


class UTAU2VS:
    def __init__(self):
        self.cvv_dict = {}
        self.c_dict = {}  # 在vc部中视为相同的辅音会以 c: c1, c2 …… 的形式被存放
        self.v_dict = {}  # 在vc部中视为相同的元音会以 v: v1, v2 …… 的形式被存放
        self.OTO_list = []
        self.VSDXMF_list = []
        self.log_list = []
        self.lsd = ''
        self.rename_dict = {}
        self.config = {}

    def oto2vsdxmf(self, begin_sign=None, ending_sign=None):
        if begin_sign is None:
            begin_sign = self.config['begin_sign']
        if ending_sign is None:
            ending_sign = self.config['ending_sign']

        # 五个集合用来检查是否缺少音素和未转换的oto
        _c_set = set(x[-2] for x in self.cvv_dict.values())
        v__set = set(x[-1] for x in self.cvv_dict.values())
        vc_set, cv_set = set(), set(cvv for cvv in self.cvv_dict.keys())
        for c in list(_c_set):
            for v in list(v__set):
                vc_set.add('{} {}'.format(v, c))
        unconvert_oto_dict = {}

        for idx, OTO in enumerate(self.OTO_list):
            alien = OTO.alien
            wav = OTO.wav
            digit_param = [y for y in self.convert_digit(*[x for x in OTO[-5:]])]
            if alien.startswith(begin_sign + ' '):
                alien = alien.split(' ')[1]
                try:
                    form_c = self.cvv_dict[alien][-2]
                    if form_c in _c_set:
                        alien = ' ' + form_c
                        self.VSDXMF_list.append(VSDXMF(alien, wav, *digit_param))
                        _c_set.discard(form_c)
                except KeyError:
                    unconvert_oto_dict[idx] = OTO
                    continue
            elif alien.endswith(' ' + ending_sign):
                actual_v = alien.split(' ')[0]
                alien = actual_v + ' '
                self.VSDXMF_list.append(VSDXMF(alien, wav, *digit_param))
                v__set.discard(actual_v)
                if actual_v in self.v_dict:
                    for form_v in self.v_dict[actual_v]:
                        form_alien = form_v + ' '
                        self.VSDXMF_list.append(VSDXMF(form_alien, '#' + alien, *digit_param))
                        v__set.discard(form_v)
            elif ' ' in alien:
                actual_v, actual_c = alien.split(' ')[0], alien.split(' ')[1]
                # 检查是否为vv，如[a あ]需要转换为[a a]
                if actual_c in self.cvv_dict:
                    if self.cvv_dict[actual_c][0] == self.cvv_dict[actual_c][1]:
                        actual_c = self.cvv_dict[actual_c][1]
                    else:
                        # 如果不是vv部则应该为vcv音素，不进行转化
                        unconvert_oto_dict[idx] = OTO
                        continue
                alien = '{} {}'.format(actual_v, actual_c)
                self.VSDXMF_list.append(VSDXMF(alien, wav, *digit_param))
                vc_set.discard(alien)
                if actual_v in self.v_dict:
                    for form_v in self.v_dict[actual_v]:
                        phoneme = form_v + ' ' + actual_c
                        self.VSDXMF_list.append(VSDXMF(phoneme, '#' + alien, *digit_param))
                        vc_set.discard(phoneme)
                if actual_c in self.c_dict:
                    for form_c in self.c_dict[actual_c]:
                        phoneme = actual_v + ' ' + form_c
                        self.VSDXMF_list.append(VSDXMF(phoneme, '#' + alien, *digit_param))
                        vc_set.discard(phoneme)
                if actual_v in self.v_dict and actual_c in self.c_dict:
                    for form_v in self.v_dict[actual_v]:
                        for form_c in self.c_dict[actual_c]:
                            phoneme = form_v + ' ' + form_c
                            self.VSDXMF_list.append(VSDXMF(phoneme, '#' + alien, *digit_param))
                            vc_set.discard(phoneme)
            elif ' ' not in alien:
                try:
                    form_c, form_v = self.cvv_dict[alien][-2], self.cvv_dict[alien][-1]
                    phoneme = form_c + ' ' + form_v
                    self.VSDXMF_list.append(VSDXMF(phoneme, wav, *digit_param))
                    cv_set.discard(alien)
                except KeyError:
                    unconvert_oto_dict[idx] = OTO
                    continue
            else:
                unconvert_oto_dict[idx] = OTO

        self.log_list = [unconvert_oto_dict, _c_set, v__set, vc_set, cv_set]

    def presamp2lsd(self):
        for key, value in self.cvv_dict.items():
            c, v = value[-2], value[-1]
            if c == v:
                self.lsd += '{}\n#{}\n'.format(key, v)
            else:
                self.lsd += '{}\n{}#{}\n'.format(key, c, v)

    def convert_digit(self, l, con, r, pre, ovl, reverse=False):
        if not reverse:
            vs_con = l + con
            vs_r = l - r
            vs_pre = l + pre
            vs_ovl = l + ovl
            return l, vs_pre, vs_con, vs_r, vs_ovl

    def rename_phoneme(self, rename_file=None):
        if self.config['presamp_file'] is None:
            return

        if rename_file is None:
            rename_file = r'{}'.format(self.config['rename_file'])
            if rename_file == 'None':
                rename_file = None
        encoding = self.config['encoding']

        if rename_file:
            with open(rename_file, mode='r', encoding=encoding) as f:
                for line in f.read().split('\n'):
                    if line:
                        cvv, c, v = line.split(',')
                        self.cvv_dict[cvv] = (*self.cvv_dict[cvv][:2], c, v)
                        if self.cvv_dict[cvv][0] != c:
                            self.c_dict.setdefault(self.cvv_dict[cvv][0], set()).add(c)
                        if self.cvv_dict[cvv][1] != v:
                            self.v_dict.setdefault(self.cvv_dict[cvv][1], set()).add(v)

        phoneme_dict = {}
        for key in self.cvv_dict.keys():
            phoneme = (self.cvv_dict[key][-2], self.cvv_dict[key][-1])
            phoneme_dict.setdefault(phoneme, []).append(key)

        edited = 'n'
        for key in phoneme_dict.keys():
            if len(ls := phoneme_dict[key]) > 1:
                print('以下整音含有相同的标记[{} {}]:'.format(key[-2], key[-1]))
                print(', '.join(ls))
                unchanged = input('请选择不需改变的整音（不输入则默认第一位不变）：')
                if not unchanged:
                    unchanged = ls[0]
                for cvv in ls:
                    if cvv == unchanged:
                        continue
                    new_phoneme = input('请给{}输入新的标记（格式为“辅音 元音”）：'.format(cvv))
                    self.cvv_dict[cvv] = (*self.cvv_dict[cvv][:2], *new_phoneme.split(' '))
                    if key[0] != new_phoneme.split(' ')[0]:
                        self.c_dict.setdefault(key[0], set()).add(new_phoneme.split(' ')[0])
                    if key[1] != new_phoneme.split(' ')[1]:
                        self.v_dict.setdefault(key[1], set()).add(new_phoneme.split(' ')[1])
                edited = 'y'
        if edited == 'y':
            confirm = input('为了新的标记没有重复，需要重新检查一遍吗（y/n）？')
            if confirm == 'y':
                self.rename_phoneme()
            if edited == 'y' and confirm == 'n':
                print('重复标记处理完毕')
                for key, value in self.cvv_dict.items():
                    if len(value) > 2:
                        self.rename_dict[key] = value[-2:]
        if edited == 'n':
            print('重复标记处理完毕')
            for key, value in self.cvv_dict.items():
                if len(value) > 2:
                    self.rename_dict[key] = value[-2:]

    def read_oto(self, oto_file=None, custom_suffix=None):
        if oto_file is None:
            oto_file = self.config['oto_file']
        if custom_suffix is None:
            if (custom_suffix := self.config['custom_suffix']) == 'None':
                custom_suffix = None
        encoding = self.config['encoding']
        scale_suffix = set()
        scale = ['A', 'A#', 'B', 'C', 'C#', 'D', 'D#',
                 'E', 'F', 'F#', 'G', 'G#']
        for n in range(11):
            for s in scale:
                scale_suffix.add(s + str(n))
        suffix_set = scale_suffix
        if custom_suffix:
            suffix_set.update(custom_suffix.split(','))

        with open(oto_file, mode='r', encoding=encoding) as f:
            otos = f.read()
        for oto in otos.split('\n'):
            if oto:
                wav = oto.split('=')[0]
                other_param = oto.split('=')[1].split(',')
                big_alien = other_param[0]
                alien = ''
                suffix = None
                for suff in suffix_set:
                    if big_alien.endswith(suff):
                        alien = big_alien[:-len(suff)]
                        suffix = suff
                if not alien:
                    alien = big_alien
                digit_param = []
                del other_param[0]
                for param in other_param:
                    digit_param.append(float(param))
                prefix = None
                self.OTO_list.append(OTO(wav, prefix, alien, suffix, *digit_param))

    def read_presamp(self, presamp_file=None, encoding=None):
        if self.config['presamp_file'] is None:
            return

        if presamp_file is None:
            presamp_file = r'{}'.format(self.config['presamp_file'])
        if encoding is None:
            encoding = self.config['encoding']
        with open(presamp_file, mode='r', encoding=encoding) as f:
            presamp = f.read()
        vowel = re.search(r'\[VOWEL][^\[]*', presamp).group(0)
        consonant = re.search(r'\[CONSONANT][^\[]*', presamp).group(0)
        vowel_dict, consonant_dict = {}, {}
        if vowel:
            for line in vowel.split('\n'):
                if line == '' or line == '[VOWEL]':
                    continue
                ls = line.split('=')
                for cvv in ls[2].split(','):
                    vowel_dict[cvv] = ls[0]
        if consonant:
            for line in consonant.split('\n'):
                if line == '' or line == '[CONSONANT]':
                    continue
                ls = line.split('=')
                for cvv in ls[1].split(','):
                    consonant_dict[cvv] = ls[0]
        for key in consonant_dict.keys():
            self.cvv_dict[key] = (consonant_dict[key], vowel_dict[key])

    def export_config(self, lsd_file=None, vsdxmf_file=None, rename_file=None):
        if lsd_file is None:
            lsd_file = r'{}'.format(self.config['lsd_file'])
        if vsdxmf_file is None:
            vsdxmf_file = r'{}'.format(self.config['vsdxmf_file'])
        if rename_file is None:
            rename_file = r'{}'.format(self.config['rename_file'])
            if rename_file == 'None':
                rename_file = 'rename.txt'

        with open(lsd_file, mode='w', encoding='utf-8') as f:
            f.write(self.lsd)

        with open(vsdxmf_file, mode='w', encoding='utf-8') as f:
            s_vsdxmf = ''
            for vsdxmf in self.VSDXMF_list:
                s_vsdxmf += ','.join(str(x) for x in vsdxmf)
                s_vsdxmf += '\n'
            f.write(s_vsdxmf)

        with open(rename_file, mode='w', encoding='utf-8') as f:
            s_rename = ''
            for key, value in self.rename_dict.items():
                s_rename += ','.join([key, *value])
                s_rename += '\n'
            f.write(s_rename)

    def export_log(self, log_file=None):
        log = ''
        unconvert_oto_dict, _c_set, v__set, vc_set, cv_set = self.log_list

        log += '--------未转化oto--------\n'
        if unconvert_oto_dict:
            for idx, oto in unconvert_oto_dict.items():
                log += '第{}行：{}\n'.format(idx, ','.join(str(x) for x in oto))
        else:
            log += '无\n'

        log += '\n\n\n--------缺少的cv部--------\n'
        if cv_set:
            for cvv in cv_set:
                log += '{}, '.format(cvv)
        else:
            log += '无\n'

        log += '\n\n\n--------缺少的开头辅音--------\n'
        if _c_set:
            for c in list(_c_set):
                log += '{}, '.format(c)
        else:
            log += '无\n'

        log += '\n\n\n--------缺少的结尾元音--------\n'
        if v__set:
            for v in list(v__set):
                log += '{}, '.format(v)
        else:
            log += '无\n'

        log += '\n\n\n--------缺少的vc部--------\n'
        if vc_set:
            for vc in list(vc_set):
                log += '{}, '.format(vc)
        else:
            log += '无\n'

        if log_file is None:
            log_file = r'{}'.format(self.config['log_file'])
        with open(log_file, mode='w', encoding='utf-8') as f:
            f.write(log)

    def utau2vs(self):
        self.read_config()
        self.read_oto()
        self.read_presamp()
        self.rename_phoneme()
        self.oto2vsdxmf()
        self.presamp2lsd()
        self.export_config()
        self.export_log()

    def read_config(self, config='config.ini'):
        conf = configparser.ConfigParser()
        conf.read(config)
        for section in conf.sections():
            self.config.update(conf.items(section))

        if self.config['presamp_file'] == 'None':
            self.config['presamp_file'] = None
            with open('JPN.txt', mode='r', encoding='utf-8') as f:
                for line in f.read().split('\n'):
                    cv, c, v = line.split(',')
                    self.cvv_dict[cv] = (c, v)


if __name__ == '__main__':
    convertor = UTAU2VS()
    convertor.utau2vs()
    with open(r'{}'.format(convertor.config['log_file']), mode='r', encoding='utf-8') as f:
        print(f.read())
    input('处理完毕，按任意键结束')
