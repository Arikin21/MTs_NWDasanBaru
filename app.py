from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('madrasah.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    
    # 1. Data Siswa
    siswa_list = conn.execute("SELECT * FROM siswa WHERE status_siswa = 'Aktif' ORDER BY nama ASC").fetchall()
    total_siswa = len(siswa_list)
    
    # 2. Statistik Keuangan SPP
    total_spp = conn.execute("SELECT SUM(jumlah) FROM spp").fetchone()[0] or 0
    
    # 3. Statistik Surat (Persuratan)
    total_surat_masuk = conn.execute("SELECT COUNT(*) FROM surat_masuk").fetchone()[0] or 0
    total_surat_keluar = conn.execute("SELECT COUNT(*) FROM surat_keluar").fetchone()[0] or 0
    total_arsip_surat = total_surat_masuk + total_surat_keluar
    
    # 4. Statistik Poin Kedisiplinan
    total_pelanggaran = conn.execute("SELECT SUM(poin) FROM poin_siswa WHERE jenis = 'Pelanggaran'").fetchone()[0] or 0
    total_prestasi = conn.execute("SELECT SUM(poin) FROM poin_siswa WHERE jenis = 'Prestasi'").fetchone()[0] or 0
    
    conn.close()
    
    # Kirim semua variabel statistik ke index.html
    return render_template('index.html', 
                           siswa=siswa_list, 
                           total_siswa=total_siswa, 
                           total_spp=total_spp,
                           total_surat=total_arsip_surat,
                           pelanggaran=total_pelanggaran,
                           prestasi=total_prestasi)

@app.route('/tambah', methods=['POST'])
def tambah_siswa():
    nis = request.form['nis']
    nisn = request.form['nisn']
    nama = request.form['nama'].upper()
    kelas = request.form['kelas']
    tempat_lahir = request.form['tempat_lahir']
    tanggal_lahir = request.form['tanggal_lahir']
    alamat = request.form['alamat']
    nama_wali = request.form['nama_wali']
    no_hp_wali = request.form['no_hp_wali']
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO siswa (nis, nisn, nama, kelas, tempat_lahir, tanggal_lahir, alamat, nama_wali, no_hp_wali, status_siswa) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Aktif')
        ''', (nis, nisn, nama, kelas, tempat_lahir, tanggal_lahir, alamat, nama_wali, no_hp_wali))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    return redirect(url_for('index'))

@app.route('/hapus/<int:id>')
def hapus(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM siswa WHERE id = ?', (id,))
    conn.execute('DELETE FROM spp WHERE siswa_id = ?', (id,))
    conn.execute('DELETE FROM absensi WHERE siswa_id = ?', (id,))
    conn.execute('DELETE FROM poin_siswa WHERE siswa_id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/edit/<int:id>')
def edit(id):
    conn = get_db_connection()
    s = conn.execute('SELECT * FROM siswa WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('edit.html', s=s)

@app.route('/update/<int:id>', methods=['POST'])
def update(id):
    nis = request.form['nis']
    nama = request.form['nama'].upper()
    kelas = request.form['kelas']
    tempat_lahir = request.form['tempat_lahir']
    tanggal_lahir = request.form['tanggal_lahir']
    alamat = request.form['alamat']
    nama_wali = request.form['nama_wali']
    no_hp_wali = request.form['no_hp_wali']
    status_siswa = request.form.get('status_siswa', 'Aktif')
    conn = get_db_connection()
    conn.execute('''
        UPDATE siswa SET 
        nis = ?, nama = ?, kelas = ?, tempat_lahir = ?, tanggal_lahir = ?, alamat = ?, nama_wali = ?, no_hp_wali = ?, status_siswa = ? 
        WHERE id = ?
    ''', (nis, nama, kelas, tempat_lahir, tanggal_lahir, alamat, nama_wali, no_hp_wali, status_siswa, id))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/spp')
def keuangan_spp():
    conn = get_db_connection()
    siswa_list = conn.execute("SELECT * FROM siswa WHERE status_siswa = 'Aktif' ORDER BY nama ASC").fetchall()
    riwayat_spp = conn.execute('''
        SELECT spp.id, siswa.nama, siswa.kelas, spp.bulan, spp.jumlah, spp.tanggal_bayar 
        FROM spp JOIN siswa ON spp.siswa_id = siswa.id ORDER BY spp.id DESC
    ''').fetchall()
    total_dana = conn.execute('SELECT SUM(jumlah) FROM spp').fetchone()[0] or 0
    conn.close()
    return render_template('spp.html', siswa=siswa_list, riwayat=riwayat_spp, total_dana=total_dana)

@app.route('/bayar', methods=['POST'])
def bayar_spp():
    siswa_id = request.form['siswa_id']
    bulan = request.form['bulan']
    jumlah = request.form['jumlah']
    if siswa_id and bulan and jumlah:
        conn = get_db_connection()
        conn.execute('INSERT INTO spp (siswa_id, bulan, jumlah) VALUES (?, ?, ?)', (siswa_id, bulan, jumlah))
        conn.commit()
        conn.close()
    return redirect(url_for('keuangan_spp'))

@app.route('/absensi', methods=['GET', 'POST'])
def absensi():
    conn = get_db_connection()
    kelas_filter = request.form.get('kelas', '')
    tanggal_filter = request.form.get('tanggal', datetime.today().strftime('%Y-%m-%d'))
    siswa_list = []
    if kelas_filter:
        siswa_list = conn.execute('''
            SELECT s.id, s.nis, s.nama, s.kelas,
            (SELECT COUNT(*) FROM absensi WHERE siswa_id = s.id AND status = 'Sakit') as sakit,
            (SELECT COUNT(*) FROM absensi WHERE siswa_id = s.id AND status = 'Izin') as izin,
            (SELECT COUNT(*) FROM absensi WHERE siswa_id = s.id AND status = 'Alpha') as alpha
            FROM siswa s WHERE s.kelas = ? AND s.status_siswa = 'Aktif' ORDER BY s.nama ASC
        ''', (kelas_filter,)).fetchall()
    riwayat_absen = conn.execute('''
        SELECT a.tanggal, s.nama, s.kelas, a.status, a.keterangan FROM absensi a
        JOIN siswa s ON a.siswa_id = s.id ORDER BY a.id DESC LIMIT 30
    ''').fetchall()
    conn.close()
    return render_template('absensi.html', siswa=siswa_list, riwayat=riwayat_absen, kelas_filter=kelas_filter, tanggal_filter=tanggal_filter)

@app.route('/simpan_absensi', methods=['POST'])
def simpan_absensi():
    tanggal = request.form['tanggal']
    kelas = request.form['kelas']
    conn = get_db_connection()
    siswa_kelas = conn.execute("SELECT id FROM siswa WHERE kelas = ? AND status_siswa = 'Aktif'", (kelas,)).fetchall()
    for s in siswa_kelas:
        status = request.form.get(f'status_{s["id"]}', 'Hadir')
        keterangan = request.form.get(f'ket_{s["id"]}', '')
        conn.execute('DELETE FROM absensi WHERE siswa_id = ? AND tanggal = ?', (s['id'], tanggal))
        conn.execute('INSERT INTO absensi (siswa_id, tanggal, status, keterangan) VALUES (?, ?, ?, ?)',
                     (s['id'], tanggal, status, keterangan))
    conn.commit()
    conn.close()
    return redirect(url_for('absensi'))

@app.route('/poin')
def manajemen_poin():
    conn = get_db_connection()
    siswa_list = conn.execute("SELECT * FROM siswa WHERE status_siswa = 'Aktif' ORDER BY nama ASC").fetchall()
    rekap_poin = conn.execute('''
        SELECT s.id, s.nis, s.nama, s.kelas,
        COALESCE((SELECT SUM(poin) FROM poin_siswa WHERE siswa_id = s.id AND jenis = 'Pelanggaran'), 0) as total_pelanggaran,
        COALESCE((SELECT SUM(poin) FROM poin_siswa WHERE siswa_id = s.id AND jenis = 'Prestasi'), 0) as total_prestasi
        FROM siswa s WHERE s.status_siswa = 'Aktif' ORDER BY s.nama ASC
    ''').fetchall()
    jurnal_poin = conn.execute('''
        SELECT p.id, s.nama, s.kelas, p.jenis, p.nama_kasus, p.poin, p.tanggal 
        FROM poin_siswa p JOIN siswa s ON p.siswa_id = s.id ORDER BY p.id DESC LIMIT 30
    ''').fetchall()
    conn.close()
    return render_template('poin.html', siswa=siswa_list, rekap=rekap_poin, jurnal=jurnal_poin)

@app.route('/simpan_poin', methods=['POST'])
def simpan_poin():
    siswa_id = request.form['siswa_id']
    jenis = request.form['jenis']
    nama_kasus = request.form['nama_kasus']
    poin = request.form['poin']
    tanggal = request.form['tanggal']
    if siswa_id and jenis and nama_kasus and poin and tanggal:
        conn = get_db_connection()
        conn.execute('INSERT INTO poin_siswa (siswa_id, jenis, nama_kasus, poin, tanggal) VALUES (?, ?, ?, ?, ?)',
                     (siswa_id, jenis, nama_kasus, poin, tanggal))
        conn.commit()
        conn.close()
    return redirect(url_for('manajemen_poin'))

@app.route('/hapus_poin/<int:id>')
def hapus_poin(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM poin_siswa WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_poin'))

@app.route('/alumni')
def data_alumni():
    conn = get_db_connection()
    alumni_list = conn.execute("SELECT * FROM siswa WHERE status_siswa != 'Aktif' ORDER BY nama ASC").fetchall()
    conn.close()
    return render_template('alumni.html', alumni=alumni_list)

@app.route('/sarpras')
def manajemen_sarpras():
    conn = get_db_connection()
    barang_list = conn.execute('SELECT * FROM inventaris ORDER BY nama_barang ASC').fetchall()
    log_pinjam = conn.execute('''
        SELECT pa.id, inv.nama_barang, pa.peminjam, pa.keperluan, pa.tanggal_pinjam, pa.tanggal_kembali
        FROM peminjaman_aset pa JOIN inventaris inv ON pa.inventaris_id = inv.id ORDER BY pa.id DESC LIMIT 40
    ''').fetchall()
    conn.close()
    return render_template('sarpras.html', barang=barang_list, log=log_pinjam)

@app.route('/tambah_aset', methods=['POST'])
def tambah_aset():
    kode_barang = request.form['kode_barang'].upper()
    nama_barang = request.form['nama_barang'].upper()
    sumber_dana = request.form['sumber_dana']
    jumlah_total = int(request.form['jumlah_total'])
    kondisi_baik = int(request.form['kondisi_baik'])
    kondisi_rusak = jumlah_total - kondisi_baik
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO inventaris (kode_barang, nama_barang, sumber_dana, jumlah_total, kondisi_baik, kondisi_rusak) VALUES (?, ?, ?, ?, ?, ?)',
                     (kode_barang, nama_barang, sumber_dana, jumlah_total, kondisi_baik, kondisi_rusak))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    return redirect(url_for('manajemen_sarpras'))

@app.route('/pinjam_aset', methods=['POST'])
def pinjam_aset():
    inventaris_id = request.form['inventaris_id']
    peminjam = request.form['peminjam'].upper()
    keperluan = request.form['keperluan']
    tanggal_pinjam = request.form['tanggal_pinjam']
    if inventaris_id and peminjam and tanggal_pinjam:
        conn = get_db_connection()
        conn.execute("INSERT INTO peminjaman_aset (inventaris_id, peminjam, keperluan, tanggal_pinjam, tanggal_kembali) VALUES (?, ?, ?, ?, 'Belum Kembali')",
                     (inventaris_id, peminjam, keperluan, tanggal_pinjam))
        conn.commit()
        conn.close()
    return redirect(url_for('manajemen_sarpras'))

@app.route('/kembalikan_aset/<int:id>')
def kembalikan_aset(id):
    hari_ini = datetime.today().strftime('%Y-%m-%d')
    conn = get_db_connection()
    conn.execute("UPDATE peminjaman_aset SET tanggal_kembali = ? WHERE id = ?", (hari_ini, id))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_sarpras'))

@app.route('/hapus_aset/<int:id>')
def hapus_aset(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM inventaris WHERE id = ?', (id,))
    conn.execute('DELETE FROM peminjaman_aset WHERE inventaris_id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_sarpras'))

@app.route('/persuratan')
def manajemen_persuratan():
    conn = get_db_connection()
    masuk = conn.execute('SELECT * FROM surat_masuk ORDER BY id DESC').fetchall()
    keluar = conn.execute('SELECT * FROM surat_keluar ORDER BY id DESC').fetchall()
    next_id_row = conn.execute("SELECT seq FROM sqlite_sequence WHERE name='surat_keluar'").fetchone()
    next_id = (next_id_row[0] + 1) if next_id_row else 1
    conn.close()
    return render_template('persuratan.html', surat_masuk=masuk, surat_keluar=keluar, next_id=next_id)

@app.route('/tambah_surat_masuk', methods=['POST'])
def tambah_surat_masuk():
    nomor_surat_asal = request.form['nomor_surat_asal']
    asal_instansi = request.form['asal_instansi'].upper()
    perihal = request.form['perihal']
    tanggal_surat = request.form['tanggal_surat']
    tanggal_terima = request.form['tanggal_terima']
    disposisi = request.form.get('disposisi', 'Belum Ada Instruksi')
    conn = get_db_connection()
    conn.execute('INSERT INTO surat_masuk (nomor_surat_asal, asal_instansi, perihal, tanggal_surat, tanggal_terima, disposisi) VALUES (?, ?, ?, ?, ?, ?)',
                 (nomor_surat_asal, asal_instansi, perihal, tanggal_surat, tanggal_terima, disposisi))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_persuratan'))

@app.route('/tambah_surat_keluar', methods=['POST'])
def tambah_surat_keluar():
    tujuan_instansi = request.form['tujuan_instansi'].upper()
    perihal = request.form['perihal']
    tanggal_kirim = request.form['tanggal_kirim']
    kode_klasifikasi = request.form['kode_klasifikasi']
    tahun_sekarang = datetime.today().strftime('%Y')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO surat_keluar (nomor_surat_keluar, tujuan_instansi, perihal, tanggal_kirim, kode_klasifikasi) VALUES (?, ?, ?, ?, ?)',
                 ('PENDING', tujuan_instansi, perihal, tanggal_kirim, kode_klasifikasi))
    inserted_id = cursor.lastrowid
    nomor_otomatis = f"{inserted_id:03d}/MA.NW.DB/{kode_klasifikasi}/{tahun_sekarang}"
    conn.execute('UPDATE surat_keluar SET nomor_surat_keluar = ? WHERE id = ?', (nomor_otomatis, inserted_id))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_persuratan'))

@app.route('/update_disposisi/<int:id>', methods=['POST'])
def update_disposisi(id):
    disposisi_baru = request.form['disposisi']
    conn = get_db_connection()
    conn.execute('UPDATE surat_masuk SET disposisi = ? WHERE id = ?', (disposisi_baru, id))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_persuratan'))

@app.route('/hapus_surat_masuk/<int:id>')
def hapus_surat_masuk(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM surat_masuk WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_persuratan'))

@app.route('/hapus_surat_keluar/<int:id>')
def hapus_surat_keluar(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM surat_keluar WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_persuratan'))

@app.route('/guru')
def manajemen_guru():
    conn = get_db_connection()
    guru_list = conn.execute('SELECT * FROM guru ORDER BY nama_guru ASC').fetchall()
    jurnal_mengajar = conn.execute('''
        SELECT ag.id, g.nama_guru, g.jabatan, ag.tanggal, ag.kelas, ag.mapel, ag.materi, ag.status_kehadiran
        FROM agenda_guru ag JOIN guru g ON ag.guru_id = g.id ORDER BY ag.id DESC LIMIT 30
    ''').fetchall()
    conn.close()
    return render_template('guru.html', guru=guru_list, jurnal=jurnal_mengajar)

@app.route('/tambah_guru', methods=['POST'])
def tambah_guru():
    nip_nuptk = request.form['nip_nuptk']
    nama_guru = request.form['nama_guru'].upper()
    jabatan = request.form['jabatan']
    status_pegawai = request.form['status_pegawai']
    no_hp_guru = request.form['no_hp_guru']
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO guru (nip_nuptk, nama_guru, jabatan, status_pegawai, no_hp_guru, status_rpp, status_silabus, status_prota, status_promes) 
            VALUES (?, ?, ?, ?, ?, 'Belum', 'Belum', 'Belum', 'Belum')
        ''', (nip_nuptk, nama_guru, jabatan, status_pegawai, no_hp_guru))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    return redirect(url_for('manajemen_guru'))

@app.route('/update_perangkat/<int:id>', methods=['POST'])
def update_perangkat(id):
    rpp = request.form['status_rpp']
    silabus = request.form['status_silabus']
    prota = request.form['status_prota']
    promes = request.form['status_promes']
    conn = get_db_connection()
    conn.execute('''
        UPDATE guru SET status_rpp = ?, status_silabus = ?, status_prota = ?, status_promes = ?
        WHERE id = ?
    ''', (rpp, silabus, prota, promes, id))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_guru'))

@app.route('/simpan_agenda', methods=['POST'])
def simpan_agenda():
    guru_id = request.form['guru_id']
    tanggal = request.form['tanggal']
    status_kehadiran = request.form['status_kehadiran']
    kelas = request.form.get('kelas', '-')
    mapel = request.form.get('mapel', '-')
    materi = request.form.get('materi', '-')
    if guru_id and tanggal and status_kehadiran:
        conn = get_db_connection()
        conn.execute('INSERT INTO agenda_guru (guru_id, tanggal, kelas, mapel, materi, status_kehadiran) VALUES (?, ?, ?, ?, ?, ?)',
                     (guru_id, tanggal, kelas, mapel, materi, status_kehadiran))
        conn.commit()
        conn.close()
    return redirect(url_for('manajemen_guru'))

@app.route('/hapus_guru/<int:id>')
def hapus_guru(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM guru WHERE id = ?', (id,))
    conn.execute('DELETE FROM agenda_guru WHERE guru_id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('manajemen_guru'))

@app.route('/cetak_spp/<int:id>')
def cetak_spp(id):
    conn = get_db_connection()
    nota = conn.execute('''
        SELECT spp.id, siswa.nama, siswa.nis, siswa.kelas, spp.bulan, spp.jumlah, spp.tanggal_bayar 
        FROM spp JOIN siswa ON spp.siswa_id = siswa.id WHERE spp.id = ?
    ''', (id,)).fetchone()
    conn.close()
    return render_template('cetak_spp.html', nota=nota)

@app.route('/cetak_poin/<int:siswa_id>')
def cetak_poin(siswa_id):
    conn = get_db_connection()
    siswa = conn.execute('SELECT * FROM siswa WHERE id = ?', (siswa_id,)).fetchone()
    riwayat = conn.execute('SELECT * FROM poin_siswa WHERE siswa_id = ? ORDER BY id DESC', (siswa_id,)).fetchall()
    total_pelanggaran = conn.execute("SELECT SUM(poin) FROM poin_siswa WHERE siswa_id = ? AND jenis = 'Pelanggaran'", (siswa_id,)).fetchone()[0] or 0
    total_prestasi = conn.execute("SELECT SUM(poin) FROM poin_siswa WHERE siswa_id = ? AND jenis = 'Prestasi'", (siswa_id,)).fetchone()[0] or 0
    conn.close()
    return render_template('cetak_poin.html', s=siswa, riwayat=riwayat, pelanggaran=total_pelanggaran, prestasi=total_prestasi)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
